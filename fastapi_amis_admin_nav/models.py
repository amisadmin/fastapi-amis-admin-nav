import uuid
from datetime import datetime
from typing import Optional

from fastapi_amis_admin import amis, models
from fastapi_amis_admin.amis import PageSchema
from fastapi_amis_admin.models.fields import Field
from sqlalchemy import Column, Text, func
from sqlmodel import Relationship, SQLModel


class NavPageType(models.IntegerChoices):
    Group = 1, "页面分组"
    SchemaAPI = 2, "Amis页面API"
    Schema = 3, "Amis页面"
    Link = 4, "页面链接"
    Iframe = 5, "Iframe页面"
    Custom = 6, "自定义页面"


def parse_page_schema_type(obj: PageSchema) -> NavPageType:
    if obj.schema_:
        return NavPageType.Iframe if obj.schema_.type == "iframe" else NavPageType.Schema
    elif obj.schemaApi:
        return NavPageType.SchemaAPI
    elif obj.children:
        return NavPageType.Group
    elif obj.link:
        return NavPageType.Link
    else:
        return NavPageType.Custom


class BaseNavPage(SQLModel):
    id: int = Field(default=None, primary_key=True, nullable=False)
    update_time: Optional[datetime] = Field(
        default_factory=datetime.now,
        title="更新时间",
        sa_column_kwargs={"onupdate": func.now(), "server_default": func.now()},
    )
    type: NavPageType = Field(NavPageType.Custom, title="页面类型")
    url: str = Field(
        "",
        title="页面路径",
        amis_form_item={  # 非自定义页面, 都是只读
            "disabledOn": "!this.is_custom",
        },
    )
    label: str = Field(..., title="页面名称", max_length=20)
    icon: str = Field(default="fa fa-flash", title="页面图标", max_length=50)
    sort: int = Field(0, title="排序")
    desc: str = Field(default="", title="页面描述", max_length=400, amis_form_item="textarea")
    page_schema: str = Field(
        "{}",
        title="页面配置",
        sa_column=Column(Text, nullable=False),
        amis_form_item=amis.Editor(language="json"),
        amis_table_column=amis.TableColumn(type="json"),
    )  # 如果是菜单组, 则没有page_schema;如果是普通html页面,则是schema
    parent_id: Optional[int] = Field(None, title="上级菜单", foreign_key="system_page.id")
    unique_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()).replace("-", "")[:16],
        title="标识",
        max_length=40,
        unique=True,
    )
    tabs_mode: Optional[amis.TabsModeEnum] = Field(
        None,
        title="分组展示模式",
        description="默认为空,展示为导航菜单."
        "其他模式参考: https://aisuda.bce.baidu.com/amis/zh-CN/components/tabs#%E5%B1%95%E7%A4%BA%E6%A8%A1%E5%BC%8F",
        amis_form_item={
            "visibleOn": f"(this.is_group || this.type === {NavPageType.Group.value}) && this.type !== {NavPageType.Custom.value}"
        },
    )
    visible: bool = Field(True, title="是否可见")
    is_group: bool = Field(False, title="是否为分组")
    is_custom: bool = Field(False, title="是否自定义")
    is_active: bool = Field(True, title="是否激活")

    def as_page_schema(self) -> PageSchema:
        page = PageSchema.parse_raw(self.page_schema)
        page.label = self.label or page.label
        page.icon = self.icon or page.icon
        page.url = self.url or page.url or f"/{self.unique_id}"
        page.sort = self.sort
        if self.is_group:  # 如果是分组,则同步tabsMode
            page.tabsMode = self.tabs_mode
        page.visible = self.visible
        return page

    @classmethod
    def parse_page_schema(cls, obj: PageSchema, **kwargs):
        data = obj.dict(include={"label", "url", "icon", "sort", "visible"})
        data.update(
            {
                "page_schema": obj.amis_json(),
                "type": parse_page_schema_type(obj),
                "tabs_mode": obj.tabsMode,
            }
        )
        data.update(kwargs)
        return cls(**data)

    def as_nav_link(self) -> amis.Nav.Link:
        link = amis.Nav.Link(
            label=self.label,
            icon=self.icon,
            to=f"?parent_id={self.parent_id or ''}",
            children=[],
            value=self.id,  # type: ignore
            parent_id=self.parent_id,  # type: ignore
        )
        return link


class NavPage(BaseNavPage, table=True):
    __tablename__ = "system_page"

    parent: Optional["NavPage"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "NavPage.parent_id",
            "remote_side": "NavPage.id",
            "uselist": False,
        }
    )

    # children: List["NavPage"] = Relationship(
    #     sa_relationship_kwargs=dict(
    #         backref=backref("parent", uselist=True, remote_side="NavPage.id"),
    #     ),
    # )
