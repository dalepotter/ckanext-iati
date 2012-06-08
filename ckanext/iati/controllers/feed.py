
import datetime

from webhelpers.feedgenerator import Atom1Feed,Enclosure
from pylons import config
from urllib import urlencode

from ckan import model
from ckan.model import Session
from ckan.lib.base import BaseController, c, request, response, json, abort
from ckan.lib.helpers import date_str_to_datetime
from ckan.logic import get_action, NotFound, NotAuthorized

from ckanext.iati.lists import COUNTRIES, ORGANIZATION_TYPES

ITEMS_LIMIT = 20


def package_search(data_dict):
    context = {'model': model, 'session': model.Session,
               'user': c.user or c.author}

    if not 'sort' in data_dict:
        data_dict['sort'] = 'metadata_modified desc'

    if not 'rows' in data_dict:
        data_dict['rows'] = ITEMS_LIMIT


    query = get_action('package_search')(context,data_dict)

    return query['results']

class FeedController(BaseController):

    base_url = config.get('ckan.site_url','http://iatiregistry.org')

    def country(self,id,format='atom'):

        country_title = dict(COUNTRIES).get(id)
        if not country_title:
            abort(404,'Country or area not found')

        data_dict = {'q': 'country: %s' % id.upper() }
        results= package_search(data_dict)

        return self.output_feed(results,
                    feed_title = u'IATI Registry - %s' % country_title,
                    feed_description = u'Recently created or updated datasets on the IATI Registry for country: "%s"' % country_title,
                    feed_link = u'%s/dataset?country=%s' % (self.base_url,id),
                    feed_guid = u'tag:iatiregistry.org,2011:/feeds/country/%s.%s' % (id,format),
                    format=format,
                )


    def publisher(self,id,format='atom'):

        try:
            context = {'model': model, 'session': model.Session,
               'user': c.user or c.author}
            group_dict = get_action('group_show')(context,{'id':id})
        except NotFound:
            abort(404,'Publisher not found')
        except NotAuthorized:
            abort(401,'NotAuthorized')


        data_dict = {'q': 'groups: %s' % id }
        results= package_search(data_dict)

        return self.output_feed(results,
                    feed_title = u'IATI Registry - %s' % group_dict['title'],
                    feed_description = u'Recently created or updated datasets on the IATI Registry by publisher: "%s"' % group_dict['title'],
                    feed_link = u'%s/dataset?groups=%s' % (self.base_url,id),
                    feed_guid = u'tag:iatiregistry.org,2011:/feeds/publisher/%s.%s' % (id,format),
                    format=format,
                )


    def organisation_type(self,id,format='atom'):

        organisation_type_title = dict(ORGANIZATION_TYPES).get(id)
        if not organisation_type_title:
            abort(404,'Unknown organisation type')

        data_dict = {'q': 'publisher_organization_type: %s' % id }
        results= package_search(data_dict)

        return self.output_feed(results,
                    feed_title = u'IATI Registry - %s' % organisation_type_title,
                    feed_description = u'Recently created or updated datasets on the IATI Registry by organisations of type: "%s"' % organisation_type_title,
                    feed_link = u'%s/dataset?publisher_organization_type=%s' % (self.base_url,id),
                    feed_guid = u'tag:iatiregistry.org,2011:/feeds/organization_type/%s.%s' % (id,format),
                    format=format,
                )

    def general(self,format='atom'):
        data_dict = {'q': '*:*' }
        results= package_search(data_dict)

        return self.output_feed(results,
                    feed_title = u'IATI Registry',
                    feed_description = u'Recently created or updated datasets on the IATI Registry',
                    feed_link = u'%s/dataset' % (self.base_url),
                    feed_guid = u'tag:iatiregistry.org,2011:/feeds/registry.%s' % (format),
                    format=format,
                )


    def custom(self,format='atom'):

        q = request.params.get('q', u'')
        search_params = {}
        for (param, value) in request.params.items():
            if not param in ['q', 'page','format'] \
                    and len(value) and not param.startswith('_'):
                search_params[param] = value
                q += ' %s: "%s"' % (param, value)

        search_url_params = urlencode(search_params)

        data_dict = { 'q':q }
        results= package_search(data_dict)

        return self.output_feed(results,
                    feed_title = u'IATI Registry - Custom query',
                    feed_description = u'Recently created or updated datasets on the IATI Registry. Custom query: \'%s\'' % q,
                    feed_link = u'%s/dataset?%s' % (self.base_url,search_url_params),
                    feed_guid = u'tag:iatiregistry.org,2011:/feeds/custom.%s?%s' % (format,search_url_params),
                    format=format,
                )



    def output_feed(self,results,
                         feed_title=u'IATI Registry',
                         feed_description=u'IATI Registry',
                         feed_link=u'http://iatiregistry.org/dataset',
                         feed_guid=u'tag:iatiregistry.org,2011:/feeds',
                         format='atom'):

        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author}

        feed = Atom1Feed(
            title=feed_title,
            link=feed_link,
            description=feed_description,
            language=u'en',
            author_name=u'IATI Registry',
            author_link=u'http://iatiregistry.org',
            feed_guid=feed_guid
            )

        def item_id(pkg_id,metadata_modified):
            return 'tag:iatiregistry.org,%s:%s' % (metadata_modified,pkg_id)

        for pkg in results:
            # We need extra details, not present in the search results
            pkg_rest = get_action('package_show_rest')(context,{'id':pkg['id']})

            # All datasets should have a group, but just in case
            publisher = pkg['groups'][0]['title'] if len(pkg['groups']) else u'Unknown'
            publisher_link = u'%s/publisher/%s' % (self.base_url,pkg['groups'][0]['name']) if len(pkg['groups']) else u''

            # We don't want to get into revisions, but at least show if it's a new or updated dataset
            if pkg_rest['metadata_modified'] > pkg_rest['metadata_created']:
                status = 'updated'
            elif pkg_rest['metadata_modified'] == pkg_rest['metadata_created']:
                status = 'created'
            else:
                status = '' # Something went wrong

            feed.add_item(
                    title= '%s [%s]' % (pkg['title'],status),
                    link= u'%s/dataset/%s' % (self.base_url,pkg['name']),
                    description='%s [%s]' % (pkg['title'],status),
                    pubdate=date_str_to_datetime(pkg_rest['metadata_modified']),
                    unique_id=item_id(pkg['id'],pkg_rest['metadata_modified']),
                    author_name=publisher,
                    author_link=publisher_link,
                    categories=pkg_rest['tags'],
                    enclosure=Enclosure(
                        u'%s/api/rest/dataset/%s' % (self.base_url,pkg['name']),
                        unicode(len(json.dumps(pkg_rest))),
                        u'application/json'
                        )
                    )
        response.content_type = feed.mime_type
        return feed.writeString('utf-8')

