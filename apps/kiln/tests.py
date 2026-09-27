from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CookRun, FireHearth, ResinLot, SoftPointProbe


class DeleteChainTestCase(TestCase):
    """四条删除链路：主管可删、值守工被拒且会话不失效、数量与页面核对。"""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.supervisor = User.objects.create_user(
            "boss", "boss@pitchkiln.local", "123456", is_staff=True
        )
        cls.worker = User.objects.create_user(
            "worker", "worker@pitchkiln.local", "123456"
        )
        now = timezone.now()
        cls.lot_free = ResinLot.objects.create(
            lotCode="脂-空闲-0001",
            originPlace="松脂坳",
            arrivalKg=Decimal("100.00"),
            receivedAt=now,
        )
        cls.lot_bound = ResinLot.objects.create(
            lotCode="脂-绑定-0002",
            originPlace="桐油坑",
            arrivalKg=Decimal("200.00"),
            receivedAt=now,
        )
        cls.hearth = FireHearth.objects.create(
            lane=1, tag="灶-测", resinGrade="特级脂", phase=FireHearth.PHASE_HOLDING
        )
        cls.cook_run = CookRun.objects.create(
            hearth=cls.hearth,
            resinLot=cls.lot_bound,
            openedAt=now,
            targetSoftPointC=Decimal("88.00"),
        )
        cls.probe = SoftPointProbe.objects.create(
            run=cls.cook_run,
            sampledAt=now,
            softPointC=Decimal("96.00"),
            samplerName="值守测试",
        )

    # ---------- 工具 ----------

    def assert_denied(self, url, obj_model, obj_pk):
        """值守工删除被拒：对象仍在、不跳登录页、会话保留、提示仅主管可删。"""
        before = obj_model.objects.count()
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        for redirect_url, _ in resp.redirect_chain:
            self.assertNotIn("/login", redirect_url)
        self.assertEqual(obj_model.objects.count(), before)
        self.assertTrue(obj_model.objects.filter(pk=obj_pk).exists())
        self.assertContains(resp, "仅主管可删")
        # 会话未被清掉：仍已认证，且能继续打开看板
        self.assertTrue(resp.context["user"].is_authenticated)
        home = self.client.get(reverse("home"))
        self.assertEqual(home.status_code, 200)
        self.assertTrue(home.context["user"].is_authenticated)

    # ---------- 链一：来脂批 ----------

    def test_worker_cannot_delete_resin_lot(self):
        self.client.login(username="worker", password="123456")
        self.assert_denied(
            reverse("delete_resin_lot", args=[self.lot_free.pk]),
            ResinLot,
            self.lot_free.pk,
        )

    def test_supervisor_deletes_resin_lot_and_card_count_matches(self):
        self.client.login(username="boss", password="123456")
        before = ResinLot.objects.count()
        resp = self.client.post(
            reverse("delete_resin_lot", args=[self.lot_free.pk]), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ResinLot.objects.count(), before - 1)
        # 卡片数与数据库核对
        self.assertEqual(len(resp.context["lots"]), before - 1)
        self.assertContains(resp, "来脂批已删除")

    def test_delete_bound_resin_lot_fails_gracefully(self):
        """被值守引用的来脂批受 PROTECT 保护：报错但会话保留、页面可浏览。"""
        self.client.login(username="boss", password="123456")
        before = ResinLot.objects.count()
        resp = self.client.post(
            reverse("delete_resin_lot", args=[self.lot_bound.pk]), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ResinLot.objects.count(), before)
        self.assertContains(resp, "已绑定值守")
        self.assertTrue(resp.context["user"].is_authenticated)

    # ---------- 链二：灶台 ----------

    def test_worker_cannot_delete_hearth(self):
        self.client.login(username="worker", password="123456")
        self.assert_denied(
            reverse("delete_hearth", args=[self.hearth.pk]),
            FireHearth,
            self.hearth.pk,
        )

    def test_supervisor_deletes_hearth_and_tile_count_matches(self):
        self.client.login(username="boss", password="123456")
        before = FireHearth.objects.count()
        resp = self.client.post(
            reverse("delete_hearth", args=[self.hearth.pk]), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(FireHearth.objects.count(), before - 1)
        # 级联删掉其值守与探针
        self.assertFalse(CookRun.objects.filter(hearth_id=self.hearth.pk).exists())
        self.assertFalse(SoftPointProbe.objects.filter(run__hearth_id=self.hearth.pk).exists())
        # 瓦片数与数据库核对（看板上下文 + 网格局部刷新两处）
        self.assertEqual(len(resp.context["hearths"]), FireHearth.objects.count())
        self.assertContains(resp, "灶台已删除")
        grid = self.client.get(reverse("floor_grid"))
        self.assertEqual(grid.status_code, 200)
        self.assertEqual(
            grid.content.count(b"hearth-tile"), FireHearth.objects.count()
        )

    # ---------- 链三：值守 ----------

    def test_worker_cannot_delete_cook_run(self):
        self.client.login(username="worker", password="123456")
        self.assert_denied(
            reverse("delete_cook_run", args=[self.cook_run.pk]),
            CookRun,
            self.cook_run.pk,
        )

    def test_supervisor_deletes_cook_run(self):
        self.client.login(username="boss", password="123456")
        before = CookRun.objects.count()
        resp = self.client.post(
            reverse("delete_cook_run", args=[self.cook_run.pk]), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(CookRun.objects.count(), before - 1)
        # 探针随值守级联删除
        self.assertEqual(SoftPointProbe.objects.count(), 0)
        self.assertContains(resp, "值守已删除")

    # ---------- 链四：探针 ----------

    def test_worker_cannot_delete_probe(self):
        self.client.login(username="worker", password="123456")
        self.assert_denied(
            reverse("delete_probe", args=[self.probe.pk]),
            SoftPointProbe,
            self.probe.pk,
        )

    def test_supervisor_deletes_probe(self):
        self.client.login(username="boss", password="123456")
        before = SoftPointProbe.objects.count()
        resp = self.client.post(
            reverse("delete_probe", args=[self.probe.pk]), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(SoftPointProbe.objects.count(), before - 1)
        self.assertContains(resp, "探针已删除")

    # ---------- 未登录仍被拦截（鉴权未关闭） ----------

    def test_anonymous_still_redirected_to_login(self):
        for url in (
            reverse("delete_resin_lot", args=[self.lot_free.pk]),
            reverse("delete_hearth", args=[self.hearth.pk]),
            reverse("delete_cook_run", args=[self.cook_run.pk]),
            reverse("delete_probe", args=[self.probe.pk]),
        ):
            resp = self.client.post(url)
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/login", resp["Location"])
        self.assertEqual(FireHearth.objects.count(), 1)
        self.assertEqual(CookRun.objects.count(), 1)
        self.assertEqual(SoftPointProbe.objects.count(), 1)
        self.assertEqual(ResinLot.objects.count(), 2)
