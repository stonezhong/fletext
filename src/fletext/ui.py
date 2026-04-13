from __future__ import annotations
from dataclasses import dataclass, field
import flet as ft
import sys
from copy import copy
from typing import Any, List, Optional, get_type_hints, Callable, Tuple
from enum import Enum, auto
from uuid import uuid4
from abc import ABC, abstractmethod

#########################################################################################
# 概念
# - 组件描述符
#       是一种JSON数据，描述组件。$type字段表示组件的类型。$refid表示组件的代号
#       将来，你可以通过组件代号来寻找组件。
# 
# 在描述符中如果有属性的值是对象，且有"$type"字段，则视为一个组件的描述符。
#
# 要从UI Descriptor加载UI组件，客户端要调用函数 load_component_from_descriptor
# 
# 组件的ui property
# - 只有在访问时才计算
# - 计算的时候通过build_ui()函数获得。一旦获得，就不会再次计算了。
#
# 组件和变量的绑定, 绑定类型: 输出型。通过函数 bind_variable(variable_name, bind_type)
#       这时，这个组件的值会被传送到其绑定的变量。当组件的值变化了，这个变量的值也会变化
# 组件和变量的绑定, 绑定类型: 输入型
#       这时，这个组件的值会从被绑定的变量中读取，如果被绑定的变量的值变化了，组件的值也会变化
#########################################################################################


##########################################################
# This module helps to build flet UI based on YAML
# descriptor.
##########################################################

TYPE_FIELD  = "$type"
REFID_FIELD = "$refid"

class HANDLER_TYPE(Enum):
    ON_CLICK = auto()

@dataclass
class ValueRef:
    value: Any = None

# 解析yaml中一个字段的值
def resolve(value, refs:dict, context:dict={}):
    if isinstance(value, list):
        return [resolve(item, refs, context=context) for item in value]
    
    if isinstance(value, dict) and value.get(TYPE_FIELD) is not None:
        # 如果值是对象且有$type字段，则被视为一个子组件的描述符
        return load_component_from_descriptor(value, refs=refs, context=context)

    if not isinstance(value, str):
        return value

    # check if we are using context variable
    if value.startswith("❔"):
        return context.get(value[1:])

    # 这是一个变量    
    if value.startswith("❕"):
        path = value[1:]
        current_obj = sys.modules[__name__]
        for seg_name in path.split("."):
            current_obj = getattr(current_obj, seg_name)
        return current_obj
    
    # 其他情况，假设就是字符串
    return value

# 从descriptor加载一个组件
def load_component_from_descriptor(
    descriptor:dict, 
    refs:Optional[dict] = None, 
    context={},
) -> Component:
    if TYPE_FIELD not  in descriptor:
        raise ValueError(f"{TYPE_FIELD} not found in desscriptor")

    component_type = descriptor[TYPE_FIELD]
    if component_type not in COMPONENT_MAP:
        raise Exception(f"{component_type} is not valid UI Component type")
    
    component = COMPONENT_MAP[component_type]()
    if refs is None:
        component._refs = {}
        new_refs = component._refs
    else:
        new_refs = refs

    component.initialize_component_from_descriptor(descriptor, new_refs, context=context)
    return component

#################################################################
# 所有组件类的共同祖先
# ui:   这是指向flet ui组件。这是一个property，并且是lazy计算的。
#       它只计算一次，并且只有在第一次访问的时候才出发计算
#################################################################
@dataclass
class Component:
    _refs: Optional[dict] = None
    _ui: Optional[ft.Control] = None

    def get_child(self, refid:str)->Optional[Component]:
        if self._refs is None:
            return None
        return self._refs.get(refid)

    def set_child_handler(self, refid:str, handler_type:HANDLER_TYPE, handler) -> Component:
        child_component = self.get_child(refid)
        match handler_type:
            case HANDLER_TYPE.ON_CLICK:
                child_component.ui.on_click = handler
        return self
    

    @property
    def ui(self):
        if self._ui is not None:
            return self._ui
        self._ui = self.build_ui()
        return self._ui
    
    def get_attr_value_for_building_ui(self, property_value:Any):
        if isinstance(property_value, Component):
            return property_value.ui
        if isinstance(property_value, list):
            return [self.get_attr_value_for_building_ui(item) for item in property_value]
        if isinstance(property_value, dict):
            return {
                attr_name: self.get_attr_value_for_building_ui(attr_value) \
                    for attr_name, attr_value in property_value.items() \
                        if not attr_name.startswith("_") and attr_value is not None
                # attr_value应该是ValueRef类型的。
            }

        return property_value.value if isinstance(property_value, ValueRef) else property_value

    def build_ui(self) -> ft.Control:
        kwargs = self.get_attr_value_for_building_ui(vars(self))
        ui_class = getattr(ft, type(self).__name__)
        return ui_class(**kwargs)
   
    # 构造Component及其子类的时候，需要从JSON Descriptor中加载Component
    def initialize_component_from_descriptor(self, descriptor:dict, refs:dict, context={}):
        # 处理refid
        refid = descriptor.get(REFID_FIELD)
        if refid is not None:
            refs[refid] = self

        for field_name, field_value in descriptor.items():
            if field_name in (TYPE_FIELD, REFID_FIELD):
                continue
            setattr(self, field_name, resolve(field_value, refs, context=context))
        
@dataclass
class Text(Component):
    # see https://flet.dev/docs/controls/text
    value:                  Optional[ValueRef] = None
    size:                   Optional[ValueRef] = None
    weight:                 Optional[ValueRef] = None
    font_family:            Optional[ValueRef] = None
    selectable:             Optional[ValueRef] = None


@dataclass
class Column(Component):
    controls:               List[Component] = field(default_factory=list)
    horizontal_alignment:   Optional[ValueRef] = None
    spacing:                Optional[ValueRef] = None
    width:                  Optional[ValueRef] = None
    expand:                 Optional[ValueRef] = None
    tight:                  Optional[ValueRef] = None

@dataclass
class Row(Component):
    controls:               List[Component] = field(default_factory=list)
    alignment:              Optional[ValueRef] = None
    spacing:                Optional[ValueRef] = None
    expand:                 Optional[ValueRef] = None

@dataclass
class Container(Component):
    content:                Optional[Component] = None
    bgcolor:                Optional[ValueRef] = None
    padding:                Optional[ValueRef] = None
    border:                 Optional[ValueRef] = None
    expand:                 Optional[ValueRef] = None
    height:                 Optional[ValueRef] = None
    width:                  Optional[ValueRef] = None
    alignment:              Optional[ValueRef] = None
    border_radius:          Optional[ValueRef] = None

@dataclass
class TextField(Component):
    value:                  Optional[ValueRef] = None
    label:                  Optional[ValueRef] = None
    width:                  Optional[ValueRef] = None
    expand:                 Optional[ValueRef] = None
    font_family:            Optional[ValueRef] = None

@dataclass
class Button(Component):
    disabled:               Optional[ValueRef] = None
    content:                Optional[ValueRef] = None

@dataclass
class TextButton(Component):
    content:                Optional[ValueRef] = None

@dataclass
class IconButton(Component):
    disabled:               Optional[ValueRef] = None
    icon:                   Optional[ValueRef] = None

@dataclass
class ExpansionTile(Component):
    title:                  Optional[Component] = None
    controls:               List[Component] = field(default_factory=list)
    shape:                  Optional[ValueRef] = None

@dataclass
class MenuBar(Component):
    controls:               List[Component] = field(default_factory=list)
    style:                  Optional[ValueRef] = None
    expand:                 Optional[ValueRef] = None

@dataclass
class SubmenuButton(Component):
    content:                Optional[Component] = None
    controls:               Optional[List[Component]] = None

@dataclass
class MenuItemButton(Component):
    content:                Optional[Component] = None

@dataclass
class AlertDialog(Component):
    model:                  Optional[ValueRef] = None
    title:                  Optional[Component] = None
    content:                Optional[Component] = None
    actions:                Optional[List[Component]] = None

COMPONENT_MAP = {
    "Text":             Text,
    "Column":           Column,
    "Row":              Row,
    "Container":        Container,
    "TextField":        TextField,
    "Button":           Button,
    "TextButton":       TextButton,
    "IconButton":       IconButton,
    "ExpansionTile":    ExpansionTile,
    "MenuBar":          MenuBar,
    "SubmenuButton":    SubmenuButton,
    "MenuItemButton":   MenuItemButton,
    "AlertDialog":      AlertDialog,
}

#################################################################
# Controller控制组建的商业逻辑
# - 你可以覆盖方法`on_variable_updated`。这样，每当一个变量被修改，你可以重新
#   计算其他需要变更的变量
#################################################################
class Controller(ABC):
    _page: ft.Page
    _component: Component
    _variable_map:     Dict[str, Any]   # variable's value come from component's value
    _id: str

    def __init__(self, page: ft.Page, component: Component):
        self._id = str(uuid4())
        self._page = page
        self._component = component
        self._variable_map = {}
    
    def get_variable(self, variable_name:str) -> Any:
        return self._variable_map.get(variable_name)

    # When a component's value changed, it gets saved to _variable_map and publish message
    # about the change
    def register_input_bind(self, variable_name:str, init_value:str=""):
        refid = variable_name
        topic = f"{self._id}-{variable_name}"

        self._variable_map[variable_name] = init_value

        def on_change(e: ft.ControlEvent):
            self._variable_map[variable_name] = e.control.value
            self.on_variable_updated(variable_name)
            self._page.pubsub.send_all_on_topic(topic, e.control.value)

        self._component.get_child(refid).ui.on_change = on_change

    def _get_refid_and_property_name(self, variable_name:str) -> Tuple[str, str, str]:
        p_pos = variable_name.rfind("#")
        if p_pos > 0:
            refid = variable_name[:p_pos]
            property_name = variable_name[p_pos+1:]
        else:
            refid = variable_name
            property_name = "value"
        topic = f"{self._id}#{refid}#{property_name}"
        return (refid, property_name, topic)

    # When a variable is change, publish to subscribed component
    def register_output_bind(self, variable_name:str):
        refid, property_name, topic = self._get_refid_and_property_name(variable_name)
        def on_value_changed(topic:str, value:str):
            setattr(
                self._component.get_child(refid).ui,
                property_name,
                value
            )
            self._component.get_child(refid).ui.update()
        
        self._page.pubsub.subscribe_topic(topic, on_value_changed)
    
    def set_variable(self, variable_name:str, value:Any):
        _, _, topic = self._get_refid_and_property_name(variable_name)
        self._variable_map[variable_name] = value
        self._page.pubsub.send_all_on_topic(topic, value)

    # derived class to override it
    @abstractmethod
    def on_variable_updated(self, variable_name:str):
        pass
    
    @property
    def page(self) -> ft.Page:
        return self._page


    @property
    def component(self) -> Component:
        return self._component
