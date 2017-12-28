from app01 import models
from stark.service import v1

class DepartmentConfig(v1.StarkConfig):
    list_display = ["title","code"]


    #8. 其它列可编辑
    # def get_list_display(self):
    #     data = []
    #     if self.list_display:
    #         data.extend(self.list_display)
    #         data.append(v1.StarkConfig.delete)
    #         data.insert(0, v1.StarkConfig.checkbox)
    #     return data
    edit_link = ["title"]




v1.site.register(models.Department,DepartmentConfig)






