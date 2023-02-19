from functools import cached_property
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from fastapi_amis_admin.admin.admin import AdminGroup, PageSchemaAdmin
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from fastapi_amis_admin_nav.models import NavPage

NodeT = TypeVar("NodeT")
NodeOrDict = Union[NodeT, Dict[str, Any]]


class AmisPageManager:
    def __init__(self, session: Session):
        self.session = session

    @cached_property
    def db_pages(self) -> List[NavPage]:
        return self.session.scalars(select(NavPage)).all()

    @cached_property
    def db_pages_uid_map(self) -> Dict[str, NavPage]:
        return {page.unique_id: page for page in self.db_pages}

    @cached_property
    def db_pages_id_map(self) -> Dict[str, NavPage]:
        return {page.id: page for page in self.db_pages}

    @cached_property
    def site_page(self) -> NavPage:
        """获取根节点,有且只有一个"""
        for page in self.db_pages:
            if page.parent_id is None:
                return page
        raise ValueError("没有找到根节点")

    def site_to_db(self, admin_group: AdminGroup, parent_id: int = None):
        """将site对象的菜单页面同步的数据库中"""
        for page in self.db_pages:
            if not page.is_custom: # 如果不是自定义的,则先全部设置为未激活
                page.is_active = False
        def append_page_to_db(admin_: PageSchemaAdmin) -> Optional[int]:
            """将页面添加到数据库中"""
            if not admin_.page_schema:  # 如果不存在page_schema,则不保存到数据库
                return None
            unique_id = str(admin_.unique_id)
            page = self.db_pages_uid_map.get(unique_id)
            # print('unique_id', unique_id, page)
            if page:  # 如果存在数据库中,则读取数据库中设置,并且更新到admin
                page.is_active = True # 设置为激活
                return page.id
            # 保存到数据库
            kwargs = {
                "parent_id": parent_id,
                "unique_id": unique_id,
            }
            if isinstance(admin_, AdminGroup):
                kwargs["is_group"] = True
            new_page = NavPage.parse_page_schema(admin_.page_schema, **kwargs)
            self.session.add(new_page)
            self.session.flush()  # 刷新,获取page_id
            return new_page.id

        # 如果没有parent_id,则作为根节点添加到数据库中,并且获取parent_id
        parent_id = parent_id or append_page_to_db(admin_group)
        for admin in admin_group:
            page_id = append_page_to_db(admin)
            if isinstance(admin, AdminGroup):
                self.site_to_db(admin, page_id)

        return self

    def db_to_site(self, admin_group: AdminGroup):
        """将数据库中的菜单页面页面同步到site中"""

        def append_page_to_site(page_: NavPage, admin_: PageSchemaAdmin = None):
            """添加子级菜单"""
            group = admin_group
            if page_.parent_id:
                group, _ = admin_group.get_page_schema_child(page_.parent.unique_id)
            if not group:
                return
            if not admin_:
                admin_ = PageSchemaAdmin(group.app)
                admin_.page_schema = page_.as_page_schema()
                setattr(admin_, "unique_id", page_.unique_id)  # noqa: B010
            if group and isinstance(group, AdminGroup):
                group.append_child(admin_)

        for page in self.db_pages:
            if not page.is_custom:  # 如果不存在,并且不是自定义,则标记为未激活
                page.is_active = False
            if page.parent_id is None:  # 如果是根级,则直接更新
                admin, parent = admin_group, None
                page.visible = True  # 标记为可见
            else:
                admin, parent = admin_group.get_page_schema_child(page.unique_id)
            if admin:  # 如果存在,则更新
                print("admin 查找到Admin成功", page.unique_id, page.as_page_schema().amis_dict())
                page.is_active = True  # 将数据库标记为已激活
                admin.page_schema = page.as_page_schema()
                # 对比admin中的父级是否和数据库中的一致,不一致则更新
                if page.parent_id and parent.unique_id != page.parent.unique_id:  # 如果不是根级,并且父级不一致,则更新父级
                    # print('父级不一致', parent.unique_id, admin.unique_id)
                    # 1. 先从原来的父级中删除
                    parent.remove_child(admin.unique_id)
                    # 2. 再添加到新的父级中
                    append_page_to_site(page, admin)
            elif page.visible:  # 如果不存在,并且是激活的,则添加到site
                # print('查找失败,未注册', page.unique_id)
                append_page_to_site(page)

        return self

    def update_db_pages_parent_and_sort(self, links: List[dict], parent_id: int = None):
        """更新数据库中菜单页面的排序和父级关系
        links: amis的导航菜单数据.结构: amis.Nav.Link
        """
        for i, link in enumerate(links):
            page = self.db_pages_id_map.get(link["value"])
            if not page:
                continue
            page.sort = -1 * i  # 排序
            if page.parent_id:  # 如果不是根级,则更新父级.
                page.parent_id = parent_id or self.site_page.id  # 父级
            if link.get("children"):
                self.update_db_pages_parent_and_sort(link["children"], parent_id=page.id if page.is_group else page.parent_id)

    # 获取数据库中激活并且可见的页面
    def get_db_active_pages(self, parent_id: int = None) -> List[dict]:
        """获取数据库中的导舤链接"""
        stmt = (
            select(NavPage)
            .where(
                NavPage.is_active == True,
                NavPage.visible == True,
            )
            .order_by(NavPage.sort.desc())
        )
        pages = self.session.scalars(stmt).all()

        def handle_(page: NavPage, children: List[NavPage]) -> dict:
            link = page.as_nav_link()
            if children:
                link.children = children
            return link.amis_dict()

        return fill_children(pages, parent_id=parent_id, handle=handle_)


def fill_children(
    items: List[NodeT], parent_id: int = None, handle: Callable[[NodeT, List[NodeT]], NodeOrDict] = None
) -> List[NodeOrDict]:
    """处理父子节点关系, 递归"""
    children = []
    handle = handle or (lambda x, y: setattr(x, "children", y or []) or x)
    for child in [item for item in items if item.parent_id == parent_id]:
        items.remove(child)
        sub_children = fill_children(items, parent_id=child.id, handle=handle)
        children.append(handle(child, sub_children))
    return children
