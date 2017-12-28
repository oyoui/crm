from django.conf.urls import url, include
from django.shortcuts import HttpResponse, render, reverse, redirect
from django.utils.safestring import mark_safe
from django.forms import ModelForm
from stark.utils.page import Pagination
from django.http import QueryDict
from django.db.models import Q
from django.db.models import ForeignKey,ManyToManyField
import copy
import json


class filterOption(object):
    def __init__(self,filed_name,muti=False,condition=False,is_choice=False):
        """

        :param filed_name:
        :param muti:
        :param condition: 过滤条件
        """

        self.filed_name = filed_name
        self.muti = muti
        self.condition = condition
        self.is_choice = is_choice


    def get_queryset(self,_field):
        if self.condition:
            return _field.rel.to.objects.filter()

        return _field.rel.to.objects.all()


    def get_choices(self,_field):

       return _field.choices


class FilterRow(object):

    def __init__(self,option,data,request):
        self.option = option
        self.data = data
        self.request = request

    def __iter__(self):
        params = copy.deepcopy(self.request.GET)

        params._mutable = True
        current_id = params.get(self.option.filed_name)
        current_id_list = params.getlist(self.option.filed_name)

        # 全部  如果循环的值 在前端传过来的里面 删除
        if self.option.filed_name in params:
            origin_list = params.pop(self.option.filed_name)
            url = "{0}?{1}".format(self.request.path_info, params.urlencode())
            yield mark_safe('<a href="{0}">全部</a>'.format(url))
            params.setlist(self.option.filed_name,origin_list)
        else:
            url = "{0}?{1}".format(self.request.path_info, params.urlencode())
            yield mark_safe('<a href="{0}" class="active">全部</a>'.format(url))

        # 全部 后面的值
        for val in self.data:
            if self.option.is_choice:
                pk,text = str(val[0]),str(val[1])
            else:
                pk,text = str(val.pk),str(val)
            if not self.option.muti:
                # 单选
                params[self.option.filed_name] = pk
                url = "%s?%s"%(self.request.path_info,params.urlencode())

                if current_id == pk:
                    yield mark_safe("<a href={0} class='active'>{1}</a>".format(url, text))
                else:
                    yield mark_safe("<a href={0}>{1}</a>".format(url,text))
            else:
                # 多选
                _params = copy.deepcopy(params)
                id_list = params.getlist(self.option.filed_name)
                print(id_list,current_id_list)
                if pk in current_id_list:

                    id_list.remove(pk)
                    _params.setlist(self.option.filed_name, id_list)
                    url = "%s?%s" % (self.request.path_info, _params.urlencode())
                    yield mark_safe("<a href={0} class='active'>{1}</a>".format(url, text))
                else:

                    id_list.append(pk)
                    _params.setlist(self.option.filed_name,id_list)
                    url = "%s?%s" % (self.request.path_info, _params.urlencode())
                    yield mark_safe("<a href={0}>{1}</a>".format(url, text))


class ChangeList(object):
    def __init__(self,config,queryset):
        self.config = config

        # [checkbox,'id','name',edit,del]
        self.list_display = config.get_list_display()
        self.model_class = config.model_class
        self.request = config.request
        self.show_add_btn = config.get_show_btn()
        self.actions = config.get_actions()
        self.show_actions = config.get_show_actions()

        # 搜索用
        self.search_key = config.search_key
        self.show_search_form = config.get_show_search_form()
        self.search_form_val = config.request.GET.get(config.search_key,'')

        #分页
        current_page = self.request.GET.get('page', 1)
        total_count = queryset.count()
        page_obj = Pagination(current_page, total_count, self.request.path_info, self.request.GET, per_page_count=8)
        self.page_obj = page_obj

        self.data_list = queryset[page_obj.start:page_obj.end]

        # 组合搜索
        self.comb_filter = config.get_comb_filter()

        # 其它列作为编辑功能
        self.edit_link = config.get_edit_link()



    def modify_actions(self):
        result = []
        for func in self.actions:
            temp = {'name':func.__name__,'text':func.short_desc}
            result.append(temp)
        return result

    def add_url(self):
        return self.config.get_add_url()

    def head_list(self):
        """
        构造表头
        :return:
        """
        result = []
        # [checkbox,'id','name',edit,del]
        for field_name in self.list_display:
            if isinstance(field_name, str):
                # 根据类和字段名称，获取字段对象的verbose_name
                verbose_name = self.model_class._meta.get_field(field_name).verbose_name
            else:
                verbose_name = field_name(self.config, is_header=True)
            result.append(verbose_name)

        return result

    def body_list(self):
        # 处理表中的数据
        # [ UserInfoObj,UserInfoObj,UserInfoObj,UserInfoObj,]
        # [ UserInfo(id=1,name='alex',age=18),UserInfo(id=2,name='alex2',age=181),]
        data_list = self.data_list
        new_data_list = []
        for row in data_list:
            # row是 UserInfo(id=2,name='alex2',age=181)
            # row.id,row.name,row.age
            temp = []
            for field_name in self.list_display:
                if isinstance(field_name,str):
                    val = getattr(row,field_name) # # 2 alex2
                    # 判断是否在编辑列表中
                    if field_name in self.edit_link:
                        val = self.edit_link_url(row.pk,val)
                else:
                    val = field_name(self.config,row)
                temp.append(val)
            new_data_list.append(temp)

        return new_data_list


    # 根据列表的字符串找到数据的字段对象,判断对象是否是FK,M2M
    # 如果不是 为chioce
    def gen_comb_filter(self):
        for option in self.comb_filter:
            # item    gender
            _field = self.model_class._meta.get_field(option.filed_name)
            # _field  app04.UserInfo.gender
            if isinstance(_field,ForeignKey):
                #如果字段的类型是ForeignKey 找到他对应的类和数据
                row = FilterRow(option,option.get_queryset(_field),self.request)
            elif isinstance(_field,ManyToManyField):
                row = FilterRow(option,option.get_queryset(_field),self.request)
            else:
                #choice
                row = FilterRow(option,option.get_choices(_field),self.request)
            yield row

    # 其它列的作为编辑功能的url
    def edit_link_url(self,pk,text):
        query_str = self.request.GET.urlencode()  # page=2&nid=1
        params = QueryDict(mutable=True)
        params[self.config._query_param_key] = query_str

        return mark_safe('<a href="%s?%s">%s</a>' % (self.config.get_change_url(pk), params.urlencode(),text))


class StarkConfig(object):

    def __init__(self, model_class, site):
        self.model_class = model_class
        self.site = site

        self.request = None
        self._query_param_key = "_listfilter"
        self.search_key = "_q"


    def wrap(self, view_func):
        def inner(request, *args, **kwargs):
            self.request = request

            return view_func(request, *args, **kwargs)

        return inner


    #1. 用户访问url
    def get_urls(self):
        app_model_name = (self.model_class._meta.app_label, self.model_class._meta.model_name,)
        url_patterns = [
            url(r'^$', self.wrap(self.changelist_view), name="%s_%s_list" % app_model_name),
            url(r'^add/$', self.wrap(self.add_view), name="%s_%s_add" % app_model_name),
            url(r'^(\d+)/delete/$', self.wrap(self.delete_view), name="%s_%s_delete" % app_model_name),
            url(r'^(\d+)/change/$', self.wrap(self.change_view), name="%s_%s_change" % app_model_name),
        ]

        url_patterns.extend(self.extra_url())

        return url_patterns

    def extra_url(self):
        return []

    @property
    def urls(self):
        return self.get_urls()

    #2. 显示哪几列
    list_display = []

    def get_list_display(self):
        data = []
        if self.list_display:
            data.extend(self.list_display)
            #data.append(StarkConfig.edit)
            data.append(StarkConfig.delete)
            data.insert(0, StarkConfig.checkbox)
        return data


    #3. 是否显示增加按钮
    show_add_btn = True

    def get_show_btn(self):
        return self.show_add_btn

    #4. 编辑时候生成 input
    model_form_class = None

    def get_model_form_class(self):
        if self.model_form_class:
            return self.model_form_class
        else:
            # 方式一:
            # class AddTable(ModelForm):
            #     class Meta:
            #         model = self.model_class
            #         fields = "__all__"
            # return AddTable
            # 方式二:
            meta = type("Meta", (object,), {"model": self.model_class, "fields": "__all__"})
            AddTable = type("AddTable", (ModelForm,), {"Meta": meta})
            return AddTable

    # 5. 关键字搜索
    show_search_form = True

    def get_show_search_form(self):
        return self.show_search_form

    search_fields = []

    def get_search_fields(self):
        result = []
        if self.search_fields:
            result.extend(self.search_fields)
        return result

    def get_search_condition(self):
        key_word = self.request.GET.get(self.search_key)
        search_fields = self.get_search_fields()
        condition = Q()
        condition.connector = 'or'
        if key_word and self.get_show_search_form():
            for field_name in search_fields:
                condition.children.append((field_name, key_word))
        return condition


    # 6. action定制
    show_actions = True
    def get_show_actions(self):
        return self.show_actions

    actions = []
    def get_actions(self):
        result = []
        if self.actions:
            result.extend(self.actions)
        return result

    def modify_actions(self):
        result = []
        for func in self.get_actions():
            temp = {'name':func.__name__,'text':func.short_desc}
            result.append(temp)
        return result


    # 7. 组合搜索
    comb_filter = []
    def get_comb_filter(self):
        return self.comb_filter


    # 8. 可编辑列
    edit_link = []

    def get_edit_link(self):
        result = []
        if self.edit_link:
            result.extend(self.edit_link)
        return result




    # ############# 处理请求的方法 ################

    def changelist_view(self, request, *args, **kwargs):

        # 6. action
        if request.method == "POST":
            fun_str = request.POST.get("list_action")
            action_func = getattr(self,fun_str)
            ret = action_func(request)
            if ret:
                return ret

        # 组合搜索过滤
        comb_codition = {}
        option_list = self.get_comb_filter()
        flag = False
        for key in request.GET.keys():
            value_list = request.GET.getlist(key)
            for option in option_list:
                if option.filed_name == key:
                    flag = True

                    break
            if flag:

                comb_codition["%s__in"%key] = value_list



        queryset = self.model_class.objects.filter(self.get_search_condition()).filter(**comb_codition).distinct()
        obj = ChangeList(self,queryset)
        return render(request, 'stark/changelist.html', {'self':obj})


        # # 分页
        # current_page = request.GET.get('page', 1)
        #
        # total_count = self.model_class.objects.filter(self.get_search_condition()).count()
        # base_url = request.path_info
        # page_list = Pagination(current_page, total_count, base_url, request.GET, per_page_count=2, pager_count=5)
        # html = page_list.page_html()
        #
        #
        # #5. 搜索 判断是否可以搜索
        # self.show_search_form = self.get_show_search_form()
        # self.search_form_val = request.GET.get(self.search_key, '')
        #
        #
        #
        # # 生成表头
        #
        # head_list = []
        # for field_name in self.get_list_display():
        #     if isinstance(field_name, str):
        #         # 根据类和字段名称，获取字段对象的verbose_name
        #         verbose_name = self.model_class._meta.get_field(field_name).verbose_name
        #     else:
        #         verbose_name = field_name(self, is_header=True)
        #     head_list.append(verbose_name)
        #
        #
        # # 处理表中的数据
        # #组合搜索
        # data_list = self.model_class.objects.filter(self.get_search_condition())[page_list.start:page_list.end]
        #
        # new_data_list = []
        # for row in data_list:
        #     # row是 UserInfo(id=2,name='alex2',age=181)
        #     # row.id,row.name,row.age
        #     temp = []
        #     for field_name in self.get_list_display():
        #         if isinstance(field_name, str):
        #             val = getattr(row, field_name)  # # 2 alex2
        #         else:
        #             val = field_name(self, row)
        #         temp.append(val)
        #     new_data_list.append(temp)
        #
        # return render(request, 'stark/changelist.html',
        #               {'data_list': new_data_list, 'head_list': head_list, "add_url": self.get_add_url(),
        #                "show_add_btn": self.get_show_btn(), "page_html": html,"self":self})

    def add_view(self, request, *args, **kwargs):

        model_form_class = self.get_model_form_class()
        _popbackid = request.GET.get('_popbackid')

        if request.method == "GET":
            form = model_form_class()

            return render(request, "stark/add_view.html", {"form": form})
        else:
            form = model_form_class(request.POST)
            if form.is_valid():
                form_obj = form.save()
                if _popbackid:
                    # 是popup请求
                    # render一个页面，写自执行函数
                    result = {'id':form_obj.pk, 'text':str(form_obj),'popbackid':_popbackid }
                    return render(request,'stark/popup_response.html',{'json_result':json.dumps(result,ensure_ascii=False)})
                else:
                    return redirect(self.get_list_url())
            else:
                return render(request, "stark/add_view.html", {"form": form})

    def delete_view(self, request, nid, *args, **kwargs):
        self.model_class.objects.filter(pk=nid).delete()
        return redirect(self.get_list_url())

    def change_view(self, request, nid, *args, **kwargs):

        obj = self.model_class.objects.filter(pk=nid).first()
        if not obj:
            return redirect(self.get_list_url())
        model_form_class = self.get_model_form_class()
        if request.method == "GET":
            form = model_form_class(instance=obj)
            return render(request, "stark/change_view.html", {"form": form})
        else:
            form = model_form_class(instance=obj, data=request.POST)
            if form.is_valid:
                form.save()
                list_query_str = request.GET.get(self._query_param_key)

                list_url = "%s?%s" % (self.get_list_url(), list_query_str)

                return redirect(list_url)
            return render(request, "stark/change_view.html", {"form": form})



    # ############# 显示列表页面 ################

    def checkbox(self, obj=None, is_header=False):
        if is_header:
            return '选择'
        return mark_safe('<input type="checkbox" name="pk" value="%s" />' % (obj.id,))

    def edit(self, obj=None, is_header=False):
        if is_header:
            return '编辑'
        query_str = self.request.GET.urlencode()
        if query_str:
            params = QueryDict(mutable=True)
            params[self._query_param_key] = query_str
            return mark_safe('<a href="%s?%s">编辑</a>' % (self.get_change_url(obj.id), params.urlencode()))
        return mark_safe('<a href="%s">编辑</a>' % (self.get_change_url(obj.id)))

    def delete(self, obj=None, is_header=False):
        if is_header:
            return '删除'
        return mark_safe('<a href="%s">删除</a>' % (self.get_delete_url(obj.id)))


    # ############# 获取url ################

    def get_list_url(self):
        name = "stark:%s_%s_list" % (self.model_class._meta.app_label, self.model_class._meta.model_name)

        list_url = reverse(name)

        return list_url

    def get_change_url(self, nid):
        name = "stark:%s_%s_change" % (self.model_class._meta.app_label, self.model_class._meta.model_name)
        edit_url = reverse(name, args=(nid,))

        return edit_url

    def get_delete_url(self, nid):
        name = "stark:%s_%s_delete" % (self.model_class._meta.app_label, self.model_class._meta.model_name)

        delete_url = reverse(name, args=(nid,))
        return delete_url

    def get_add_url(self):
        name = "stark:%s_%s_add" % (self.model_class._meta.app_label, self.model_class._meta.model_name)

        add_url = reverse(name)
        return add_url


class StarkSite(object):
    def __init__(self):
        self._registey = {}

    def register(self, model_class, stark_config_class=None):
        if not stark_config_class:
            stark_config_class = StarkConfig

        self._registey[model_class] = stark_config_class(model_class, self)

    def get_urls(self):

        url_pattern = []

        for model_class, stark_config_obj in self._registey.items():
            # 为每一个类，创建4个URL
            """
            {
                models.UserInfo: StarkConfig(models.UserInfo,self),
                models.Role: StarkConfig(models.Role,self)
            }
            /stark/app01/userinfo/
            /stark/app01/userinfo/add/
            /stark/app01/userinfo/(\d+)/change/
            /stark/app01/userinfo/(\d+)/delete/
            """
            app_name = model_class._meta.app_label
            model_name = model_class._meta.model_name

            curd_url = url(r'^%s/%s/' % (app_name, model_name,), (stark_config_obj.urls, None, None))
            url_pattern.append(curd_url)

        return url_pattern

    @property
    def urls(self):
        return self.get_urls(), None, "stark"


site = StarkSite()
