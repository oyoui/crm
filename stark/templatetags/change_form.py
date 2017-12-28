from django.template import Library
from django.forms import ModelChoiceField
from django.shortcuts import reverse

register = Library()



@register.inclusion_tag('stark/form.html')
def form(model_form_obj):

    new_choice = []
    for bfield in model_form_obj:
        temp = {"is_popup": False, "item": bfield}
        if isinstance(bfield.field, ModelChoiceField):
            # 获取类名
            related_class_name = bfield.field.queryset.model
            app_model_name = related_class_name._meta.app_label, related_class_name._meta.model_name
            print(app_model_name)
            base_url = reverse("stark:%s_%s_add" % app_model_name)
            popurl = "%s?_popbackid=%s" % (base_url, bfield.auto_id)
            temp["popup_url"] = popurl
            temp["is_popup"] = True
        new_choice.append(temp)

    return {"form": new_choice}