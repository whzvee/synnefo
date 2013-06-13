# Copyright 2011-2013 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

from functools import partial

from django.http import HttpResponse
from django.utils import simplejson as json
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.contrib import messages

from astakos.im.models import AstakosUser, Service
from snf_django.lib import api
from snf_django.lib.api import faults
from astakos.im.settings import (
    INVITATIONS_ENABLED, COOKIE_NAME, EMAILCHANGE_ENABLED, QUOTAHOLDER_URL,
    PROJECTS_VISIBLE)
from astakos.im.forms import FeedbackForm
from astakos.im.functions import send_feedback as send_feedback_func

import logging
logger = logging.getLogger(__name__)

format = ('%a, %d %b %Y %H:%M:%S GMT')

absolute = lambda request, url: request.build_absolute_uri(url)


# Decorator for API methods, using common utils.api_method decorator.
# It is used for 'get_services' and 'get_menu' methods that do not
# require any sort of authentication
api_method = partial(api.api_method, user_required=False,
                     token_required=False, logger=logger)


def get_services_dict():
    """Return dictionary with information about available Services."""
    return list(Service.objects.values("id", "name", "url", "icon"))


@api_method(http_method=None)
def get_services(request):
    callback = request.GET.get('callback', None)
    mimetype = 'application/json'
    data = json.dumps(get_services_dict())

    if callback:
        # Consume session messages. When get_services is loaded from an astakos
        # page, messages should have already been consumed in the html
        # response. When get_services is loaded from another domain/service we
        # consume them here so that no stale messages to appear if user visits
        # an astakos view later on.
        # TODO: messages could be served to other services/sites in the dict
        # response of get_services and/or get_menu. Services could handle those
        # messages respectively.
        messages_list = list(messages.get_messages(request))
        mimetype = 'application/javascript'
        data = '%s(%s)' % (callback, data)

    return HttpResponse(content=data, mimetype=mimetype)


@api_method()
def get_menu(request, with_extra_links=False, with_signout=True):
    user = request.user
    index_url = reverse('index')

    if user.is_authenticated():
        l = []
        append = l.append
        item = MenuItem
        item.current_path = absolute(request, request.path)
        append(item(url=absolute(request, reverse('index')),
                    name=user.email))
        if with_extra_links:
            append(item(url=absolute(request, reverse('landing')),
                        name="Overview"))
        if with_signout:
            append(item(url=absolute(request, reverse('landing')),
                        name="Dashboard"))
        if with_extra_links:
            append(item(url=absolute(request, reverse('edit_profile')),
                        name="Profile"))

        if with_extra_links:
            if INVITATIONS_ENABLED:
                append(item(url=absolute(request, reverse('invite')),
                            name="Invitations"))

            append(item(url=absolute(request, reverse('resource_usage')),
                        name="Usage"))

            if QUOTAHOLDER_URL and PROJECTS_VISIBLE:
                append(item(url=absolute(request, reverse('project_list')),
                            name="Projects"))
            #append(item(
                #url=absolute(request, reverse('api_access')),
                #name="API Access"))

            append(item(url=absolute(request, reverse('feedback')),
                        name="Contact"))
        if with_signout:
            append(item(url=absolute(request, reverse('logout')),
                        name="Sign out"))
    else:
        l = [{'url': absolute(request, index_url),
              'name': _("Sign in")}]

    callback = request.GET.get('callback', None)
    data = json.dumps(tuple(l))
    mimetype = 'application/json'

    if callback:
        mimetype = 'application/javascript'
        data = '%s(%s)' % (callback, data)

    return HttpResponse(content=data, mimetype=mimetype)


class MenuItem(dict):
    current_path = ''

    def __init__(self, *args, **kwargs):
        super(MenuItem, self).__init__(*args, **kwargs)
        if kwargs.get('url') or kwargs.get('submenu'):
            self.__set_is_active__()

    def __setitem__(self, key, value):
        super(MenuItem, self).__setitem__(key, value)
        if key in ('url', 'submenu'):
            self.__set_is_active__()

    def __set_is_active__(self):
        if self.get('is_active'):
            return
        if self.current_path.startswith(self.get('url')):
            self.__setitem__('is_active', True)
        else:
            submenu = self.get('submenu', ())
            current = (i for i in submenu if i.get('url') == self.current_path)
            try:
                current_node = current.next()
                if not current_node.get('is_active'):
                    current_node.__setitem__('is_active', True)
                self.__setitem__('is_active', True)
            except StopIteration:
                return

    def __setattribute__(self, name, value):
        super(MenuItem, self).__setattribute__(name, value)
        if name == 'current_path':
            self.__set_is_active__()


def __get_uuid_displayname_catalogs(request, user_call=True):
    # Normal Response Codes: 200
    # Error Response Codes: BadRequest (400)

    try:
        input_data = json.loads(request.raw_post_data)
    except:
        raise faults.BadRequest('Request body should be json formatted.')
    else:
        uuids = input_data.get('uuids', [])
        if uuids == None and user_call:
            uuids = []
        displaynames = input_data.get('displaynames', [])
        if displaynames == None and user_call:
            displaynames = []
        user_obj = AstakosUser.objects
        d = {'uuid_catalog': user_obj.uuid_catalog(uuids),
             'displayname_catalog': user_obj.displayname_catalog(displaynames)}

        response = HttpResponse()
        response.content = json.dumps(d)
        response['Content-Type'] = 'application/json; charset=UTF-8'
        response['Content-Length'] = len(response.content)
        return response


def __send_feedback(request, email_template_name='im/feedback_mail.txt',
                    user=None):
    if not user:
        auth_token = request.POST.get('auth', '')
        if not auth_token:
            raise faults.BadRequest('Missing user authentication')

        try:
            user = AstakosUser.objects.get(auth_token=auth_token)
        except AstakosUser.DoesNotExist:
            raise faults.BadRequest('Invalid user authentication')

    form = FeedbackForm(request.POST)
    if not form.is_valid():
        logger.error("Invalid feedback request: %r", form.errors)
        raise faults.BadRequest('Invalid data')

    msg = form.cleaned_data['feedback_msg']
    data = form.cleaned_data['feedback_data']
    try:
        send_feedback_func(msg, data, user, email_template_name)
    except:
        return HttpResponse(status=502)
    return HttpResponse(status=200)