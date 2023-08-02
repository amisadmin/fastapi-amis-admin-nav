from typing import Any, Dict, List

from fastapi import Body
from fastapi_amis_admin import admin, amis
from fastapi_amis_admin.admin import AdminApp
from fastapi_amis_admin.amis import Form, TableCRUD
from fastapi_amis_admin.amis.components import Page, PageSchema
from fastapi_amis_admin.crud import BaseApiOut, ItemListSchema
from fastapi_amis_admin.crud.base import SchemaCreateT
from sqlalchemy.engine import Result
from starlette.requests import Request

from fastapi_amis_admin_nav.models import NavPage, NavPageType
from fastapi_amis_admin_nav.utils import AmisPageManager, include_children


class NavPageAdmin(admin.ModelAdmin):
    page_schema = PageSchema(label="页面管理", icon="fa fa-group")
    page_parser_mode = "html"  # 页面显示为iframe
    model = NavPage
    list_per_page = 100
    list_display = [
        NavPage.id,
        NavPage.label,
        NavPage.icon,
        amis.TableColumn(
            type="tpl",
            label="图标预览",
            tpl="<i class=\"cxd-Button-icon fa-2x ${icon}\"></i>",
        ),
        NavPage.url,
        NavPage.desc,
        NavPage.visible,
        NavPage.unique_id,
        NavPage.is_locked,
        NavPage.is_active,
        NavPage.update_time,
    ]

    ordering = [NavPage.parent_id, NavPage.sort.desc()]

    list_filter = [
        NavPage.visible,
        NavPage.is_custom,
        NavPage.is_group,
        NavPage.is_active,
        NavPage.is_locked,
        NavPage.parent_id,
    ]

    create_fields = [
        NavPage.type,
        NavPage.label,
        NavPage.icon,
        NavPage.url,
        NavPage.desc,
        NavPage.visible,
        NavPage.tabsMode,
        NavPage.is_locked,
        NavPage.page_schema,
    ]

    update_fields = [
        NavPage.type,
        NavPage.label,
        NavPage.icon,
        NavPage.url,
        NavPage.desc,
        NavPage.visible,
        NavPage.tabsMode,
        NavPage.is_locked,
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

    async def get_create_form(self, request: Request, bulk: bool = False) -> Form:
        form = await super().get_create_form(request, bulk)
        if not bulk:
            form.api += "?parent_id=$parent_id"
        return form

    async def on_create_pre(self, request: Request, obj: SchemaCreateT, **kwargs) -> Dict[str, Any]:
        data = await super().on_create_pre(request, obj, **kwargs)
        data["is_custom"] = True
        data["parent_id"] = request.query_params.get("parent_id")
        if data.get("type") == NavPageType.Group:
            data["is_group"] = True
        return data

    async def get_list_table(self, request: Request) -> TableCRUD:
        table = await super().get_list_table(request)
        table.defaultParams.update({"is_active": True})
        table.itemBadge = amis.Badge(
            text="Group",
            mode="ribbon",
            position="top-left",
            visibleOn="this.is_group",
        )
        return table

    async def on_list_after(self, request: Request, result: Result, data: ItemListSchema, **kwargs) -> ItemListSchema:
        data.items = self.parser.conv_row_to_dict(result.all())
        data.items = [self.list_item(item) for item in include_children(data.items)]
        return data
