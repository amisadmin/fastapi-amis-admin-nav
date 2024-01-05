from functools import cached_property
from typing import Dict, List, Optional

from fastapi_amis_admin.admin.admin import AdminGroup, PageSchemaAdmin
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from fastapi_amis_admin_nav.models import NavPage


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
    def site_page(self) -> Optional[NavPage]:
        """获取根节点,有且只有一个"""
        for page in self.db_pages:
            if page.parent_id is None:
                return page
        return None

    def site_to_db(self, admin_group: AdminGroup, parent_id: int = None):
        """将site对象的菜单页面同步的数据库中"""
        for page in self.db_pages:
            if not page.is_custom:  # 如果不是自定义的,则先全部设置为未激活
                page.is_active = False

        def append_page_to_db(admin_: PageSchemaAdmin) -> Optional[int]:
            """将页面添加到数据库中"""
            if not admin_.page_schema:  # 如果不存在page_schema,则不保存到数据库
                return None
            unique_id = str(admin_.unique_id)
            page = self.db_pages_uid_map.get(unique_id)
            # print('unique_id', unique_id, page)
            if page:  # 如果存在数据库中,则读取数据库中设置,并且更新到admin
                page.is_active = True  # 设置为激活
                if not page.is_locked:  # 判断是否锁定,如果锁定,则不更新.
                    page.update_from_page_schema(admin_.page_schema)
                return page.id
            # 保存到数据库
            kwargs = {
                "label": admin_.page_schema.label,
                "sort": admin_.page_schema.sort,
                "parent_id": parent_id,
                "unique_id": unique_id,
            }
            if isinstance(admin_, AdminGroup):
                kwargs["is_group"] = True
            new_page = NavPage(**kwargs).update_from_page_schema(admin_.page_schema)
            self.session.add(new_page)
            self.session.flush()  # 刷新,获取page_id
            return new_page.id

        if not parent_id:  # 如果没有parent_id,则作为根节点添加到数据库中,并且获取parent_id
            if not self.site_page:
                parent_id = append_page_to_db(admin_group)
            else:
                self.site_page.is_active = True
                self.site_page.unique_id = admin_group.unique_id
                parent_id = self.site_page.id
        for admin in admin_group:
            page_id = append_page_to_db(admin)
            if isinstance(admin, AdminGroup):
                self.site_to_db(admin, page_id)

        return self

    def db_to_site(self, admin_group: AdminGroup):
        """将数据库中的菜单页面页面同步到site中"""

        def append_page_to_site(page_: NavPage, admin_: PageSchemaAdmin = None) -> Optional[PageSchemaAdmin]:
            """添加子级菜单"""
            group = admin_group
            if page_.parent_id:
                if page_.parent.unique_id == admin_group.unique_id:  # 如果父级是根级,则直接添加
                    group = admin_group
                else:  # 如果父级不是根级,则先查找父级
                    group, _ = admin_group.get_page_schema_child(page_.parent.unique_id)
                if not group:  # 如果父级不存在,则不添加; 尝试先添加父级
                    group = update_page_to_site(page_.parent)
            if not group:
                return None
            if not admin_:
                admin_ = AdminGroup(group.app) if page_.is_group else PageSchemaAdmin(group.app)
                admin_.page_schema = page_.as_page_schema()
                setattr(admin_, "unique_id", page_.unique_id)  # noqa: B010
            if group and isinstance(group, AdminGroup):
                group.append_child(admin_)
                return admin_
            return None

        def update_page_to_site(page_: NavPage) -> Optional[PageSchemaAdmin]:
            """更新菜单"""
            if not page_.is_custom:  # 如果不存在,并且不是自定义,则标记为未激活
                page_.is_active = False
            if page_.parent_id is None:  # 如果是根级,则直接更新
                admin, parent = admin_group, None
                page_.visible = True  # 标记为可见
            else:
                admin, parent = admin_group.get_page_schema_child(page_.unique_id)
            if admin:  # 如果存在,则更新
                # print("admin 查找到Admin成功", page.unique_id, page.as_page_schema().amis_dict())
                page_.is_active = True  # 将数据库标记为已激活
                admin.page_schema = page_.as_page_schema()
                # 对比admin中的父级是否和数据库中的一致,不一致则更新
                if page_.parent_id and parent.unique_id != page_.parent.unique_id:  # 如果不是根级,并且父级不一致,则更新父级
                    # print('父级不一致', parent.unique_id, admin.unique_id)
                    # 1. 先从原来的父级中删除
                    parent.remove_child(admin.unique_id)
                    # 2. 再添加到新的父级中
                    return append_page_to_site(page_, admin)
            elif page_.is_active and page_.visible:  # 如果不存在,并且是激活的,则添加到site
                # print('查找失败,未注册', page_.unique_id, page_.label)
                return append_page_to_site(page_)
            return None

        for page in self.db_pages:
            update_page_to_site(page)

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
            if page.id != self.site_page.id:  # 如果不是根级,则更新父级.
                page.parent_id = parent_id or self.site_page.id  # 父级
            if link.get("children"):
                self.update_db_pages_parent_and_sort(
                    link["children"], parent_id=page.id if page.is_group else page.parent_id
                )

    # 获取数据库中激活并且可见的页面
    def get_db_active_pages(self, parent_id: int = None) -> List[dict]:
        """获取数据库中的导舤链接"""
        stmt = select(NavPage).where(NavPage.is_active == True, NavPage.visible == True).order_by(NavPage.sort.desc())
        pages = self.session.scalars(stmt)
        return include_children([page.as_nav_link().amis_dict() for page in pages], key="value")


def include_children(items: List[dict], key: str = "id", parent_key: str = "parent_id") -> List[dict]:
    """处理父子节点关系, 递归.NodeT必须有id,parent_id,children属性"""

    result: List[dict] = []

    def append_child(parent: dict, child_: dict):
        if not parent.get("children"):
            parent["children"] = []
        parent["children"].append(child_)
        return parent

    def insert_new_node(node: dict, new_items: List[dict], is_top: bool = False) -> bool:
        #  先把列表中的子节点全部找出来.
        for item in new_items.copy():
            if node[key] == item.get(parent_key, None):  # 找出新节点的子节点,添加到新节点的children中
                new_items.remove(item)
                node = append_child(node, item)
        for i, item in enumerate(new_items):
            if node.get(parent_key, None) == item[key]:  # 如果新节点的父级是当前节点,则添加到当前节点的子节点中
                new_items[i] = append_child(item, node)
                return True
            if item.get("children"):
                if insert_new_node(node, item["children"], is_top=False):
                    return True
        if is_top:
            new_items.append(node)
        return False

    for child in items:
        insert_new_node(child, result, is_top=True)

    return result
