from __future__ import annotations
from typing import Callable, Any, Dict, Optional
from abc import ABC
from .pubsub import PubSub
from uuid import uuid4

class VarEnvironment:
    variable_map: Dict[str, BindVariable]
    parent_env: Optional[VarEnvironment]
    pubsub: Optional[PubSub] = None
    name:str

    def __init__(
        self, 
        parent_env = None, 
        variable_map:Dict[str, BindVariable]={}, 
        pubsub:Optional[PubSub]=None,
        name:str="default"
    ):
        self.parent_env = parent_env
        self.variable_map = variable_map.copy()
        self.pubsub = pubsub
        self.name = name
    
    def get_value(self, name:str):
        if name in self.variable_map:
            var = self.variable_map[name]
            return var.get_value() if isinstance(var, BindVariable) else var
        return self.parent_env.get_value(name) if self.parent_env is not None else None
       
    def __getattr__(self, name:str)->BindVariable:
        return self.get_value(name)
    
    def new_settable(self, value:Any=None, name:Optional[str]=None):
        if name is None:
            name = str(uuid4())
        ret = SettableVariable(self, name, value)
        self.variable_map[name] = ret
        return ret

    def new_calculable(self, calculator:Callable[[], Any], **dependOn):
        return CalculableVariable(self, calculator, **dependOn)
    
    # 将一个SettableVariable变量发布，这样其他人可以通过发布消息来设置这个变量的值
    def publish_settable(self, name:str):
        if name not in self.variable_map:
            raise ValueError(f"There is no variable for \"{name}\"")
        var = self.variable_map[name]
        if not isinstance(var, SettableVariable):
            raise ValueError(f"Variable \"{name}\" is not settable")
        self.pubsub.subscribe(f"env.{self.name}.{name}", lambda new_value: var.set_value(new_value))

class BindVariable(ABC):
    env: VarEnvironment     # 这个变量对应的环境
    name: str               # 这个变量在环境中的名字

    def __init__(self, env:VarEnvironment, name:str):
        self.env = env
        self.name = name


# 一个可以设置的变量，它不依赖于其他变量
class SettableVariable(BindVariable):
    _value: Any

    def __init__(self, env:VarEnvironment, name:str, value:Any=None):
        super().__init__(env, name=name)
        self._value = value
  
    def get_value(self):
        return self._value
    
    def set_value(self, value:Any=None):
        self._value = value

    def publish(self) -> SettableVariable:
        if self.env.pubsub is None:
            raise ValueError("The environment is not bind to a message bus")
        print(f"subscribe: env.{self.env.name}.{self.name}")
        self.env.pubsub.subscribe(f"env.{self.env.name}.{self.name}", lambda new_value: self.set_value(new_value))
        return self


# 一个由计算得到的变量
class CalculableVariable(BindVariable):
    calculator: Callable[[], Any]

    def __init__(self, env:VarEnvironment, calculator:Callable[[], Any], name:Optional[str]=None):
        super().__init__(env, name=name)
        self.calculator = calculator
  
    def get_value(self):
        return self.calculator(self.env)
    
