from typing import Any, Dict, List

from fastapi import Body
from fastapi_amis_admin import admin, amis
from fastapi_amis_admin.admin import AdminApp
from fastapi_amis_admin.amis import AmisAPI, TableCRUD
from fastapi_amis_admin.amis.components import Page, PageSchema
from fastapi_amis_admin.crud import BaseApiOut
from fastapi_amis_admin.crud.base import SchemaModelT
from sqlalchemy.sql import Select
from starlette.requests import Request

from fastapi_amis_admin_nav.models import NavPage
from fastapi_amis_admin_nav.utils import AmisPageManager


class NavPageAdmin(admin.ModelAdmin):
    page_schema = PageSchema(label="页面管理", icon="fa fa-group")
    model = NavPage
    list_per_page = 100
    list_display = [
        NavPage.id,
        NavPage.label,
        NavPage.icon,
        NavPage.url,
        NavPage.desc,
        NavPage.visible,
        NavPage.unique_id,
        NavPage.is_active,
        NavPage.update_time,
    ]

    ordering = [NavPage.parent_id, NavPage.sort.desc()]

    list_filter = [
        NavPage.visible,
        NavPage.is_custom,
        NavPage.is_group,
        NavPage.is_active,
    ]

    create_fields = [
        NavPage.type,
        NavPage.label,
        NavPage.icon,
        NavPage.url,
        NavPage.desc,
        NavPage.visible,
        NavPage.tabs_mode,
        NavPage.page_schema,
    ]

    update_fields = [
        NavPage.type,
        NavPage.label,
        NavPage.icon,
        NavPage.url,
        NavPage.desc,
        NavPage.visible,
        NavPage.tabs_mode,
        NavPage.page_schema,
    ]

    def __init__(self, app: "AdminApp"):
        super().__init__(app)

        @self.site.fastapi.on_event("startup")
        async def sync_pages():
            await self.site.db.async_run_sync(
                lambda session: AmisPageManager(session).site_to_db(self.site).db_to_site(self.site)
            )
            await self.site.db.async_commit()

    async def get_page(self, request: Request) -> Page:
        page = await super().get_page(request)
        page.asideResizor = True
        page.aside = amis.Nav(
            name="nav",
            source=f"{self.router_path}/get_active_pages",
            draggable=True,
            dragOnSameLevel=False,
            saveOrderApi=f"{self.router_path}/update_pages",
        )
        page.title = "页面管理"
        page.toolbar = amis.ActionType.Ajax(label="更新应用页面", api=f"{self.router_path}/reload", level=amis.LevelEnum.primary)
        return page

    async def get_list_table_api(self, request: Request) -> AmisAPI:
        api = await super().get_list_table_api(request)
        api.url += "&parent_id=${parent_id}"
        return api

    async def get_select(self, request: Request) -> Select:
        sel = await super().get_select(request)
        parent_id = request.query_params.get("parent_id")
        if parent_id:  # None为根节点;
            sel = sel.where(NavPage.parent_id == parent_id)
        return sel

    def register_router(self):
        @self.router.post("/reload")
        async def reload_site_page_schema(request: Request):
            await self.db.async_run_sync(lambda session: AmisPageManager(session).db_to_site(self.site))
            return BaseApiOut(msg="success")

        @self.router.get("/get_active_pages")
        async def get_active_pages(request: Request):
            items = await self.db.async_run_sync(lambda session: AmisPageManager(session).get_db_active_pages())
            # 将根节点的子节点提取出来
            if items:
                root = items[0]
                children = items[0]["children"]
                root["children"] = []
                items = [root, *children]
            return BaseApiOut(data=items)

        @self.router.post("/update_pages")
        async def update_pages(request: Request, data: List[dict] = Body(..., embed=True)):
            await self.db.async_run_sync(lambda session: AmisPageManager(session).update_db_pages_parent_and_sort(data))
            return BaseApiOut(msg="success")

        return super().register_router()

    def create_item(self, item: Dict[str, Any]) -> SchemaModelT:
        item["is_custom"] = True
        return super().create_item(item)

    async def get_list_table(self, request: Request) -> TableCRUD:
        table = await super().get_list_table(request)
        table.defaultParams = {"is_del": False}
        table.itemBadge = amis.Badge(
            text="Group",
            mode="ribbon",
            position="top-left",
            visibleOn="this.is_group",
        )
        return table
