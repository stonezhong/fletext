from typing import List, Callable, Dict, Any
from collections import defaultdict

#########################################################################################
# 这个模块负责消息的订阅和消息的发送
#########################################################################################
class PubSub: 
    callback_registry:Dict[str, List[Callable[[], None]]] = defaultdict(list)

    # 订阅消息，一旦一个消息被发布，所有的订阅者登记注册的方法就会被处罚
    def subscribe(self, subject_id:str, callback: Callable[[], None]):
        self.callback_registry[subject_id].append(callback)

    # 发布消息
    def publish(self, subject_id, message:Any):
        for callback in self.callback_registry.get(subject_id, []):
            callback(message)
