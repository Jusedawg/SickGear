# coding=utf-8
#
# This file is part of SickGear.
#
# SickGear is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickGear is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickGear.  If not, see <http://www.gnu.org/licenses/>.

import re
import traceback

from . import generic
from sickbeard import logger, tvcache
from sickbeard.bs4_parser import BS4Parser
from sickbeard.helpers import tryInt
from lib.unidecode import unidecode


class FreshOnTVProvider(generic.TorrentProvider):

    def __init__(self):
        generic.TorrentProvider.__init__(self, 'FreshOnTV')

        self.url_base = 'https://freshon.tv/'
        self.urls = {'config_provider_home_uri': self.url_base,
                     'login': self.url_base + 'login.php?action=makelogin',
                     'search': self.url_base + 'browse.php?incldead=%s&words=0&cat=0&search=%s',
                     'get': self.url_base + '%s'}

        self.url = self.urls['config_provider_home_uri']

        self.username, self.password, self.minseed, self.minleech = 4 * [None]
        self.freeleech = False
        self.cache = FreshOnTVCache(self)

    def _authorised(self, **kwargs):

        return super(FreshOnTVProvider, self)._authorised(
            post_params={'login': 'Do it!'},
            failed_msg=(lambda x=None: 'DDoS protection by CloudFlare' in x and
                                       u'Unable to login to %s due to CloudFlare DDoS javascript check' or
                                       'Username does not exist' in x and
                                       u'Invalid username or password for %s. Check settings' or
                                       u'Failed to authenticate or parse a response from %s, abort provider'))

    def _search_provider(self, search_params, **kwargs):

        results = []
        if not self._authorised():
            return results

        items = {'Cache': [], 'Season': [], 'Episode': [], 'Propers': []}
        freeleech = (0, 3)[self.freeleech]

        rc = dict((k, re.compile('(?i)' + v))
                  for (k, v) in {'info': 'detail', 'get': 'download', 'name': '_name'}.items())
        for mode in search_params.keys():
            for search_string in search_params[mode]:

                search_string, search_url = self._title_and_url((
                    isinstance(search_string, unicode) and unidecode(search_string) or search_string,
                    self.urls['search'] % (freeleech, search_string)))

                # returns top 15 results by default, expandable in user profile to 100
                html = self.get_url(search_url)

                cnt = len(items[mode])
                try:
                    if not html or self._has_no_results(html):
                        raise generic.HaltParseException

                    with BS4Parser(html, features=['html5lib', 'permissive']) as soup:
                        torrent_table = soup.find('table', attrs={'class': 'frame'})
                        torrent_rows = [] if not torrent_table else torrent_table.find_all('tr')

                        if 2 > len(torrent_rows):
                            raise generic.HaltParseException

                        for tr in torrent_rows[1:]:
                            try:
                                if tr.find('img', alt='Nuked'):
                                    continue

                                seeders, leechers, size = [tryInt(n, n) for n in [
                                    (tr.find_all('td')[x].get_text().strip()) for x in (-2, -1, -4)]]
                                if self._peers_fail(mode, seeders, leechers):
                                    continue

                                info = tr.find('a', href=rc['info'], attrs={'class': rc['name']})
                                title = 'title' in info.attrs and info.attrs['title'] or info.get_text().strip()

                                download_url = self.urls['get'] % str(tr.find('a', href=rc['get'])['href']).lstrip('/')
                            except (AttributeError, TypeError, ValueError):
                                continue

                            if title and download_url:
                                items[mode].append((title, download_url, seeders, self._bytesizer(size)))

                except generic.HaltParseException:
                    pass
                except Exception:
                    logger.log(u'Failed to parse. Traceback: %s' % traceback.format_exc(), logger.ERROR)
                self._log_search(mode, len(items[mode]) - cnt, search_url)

            self._sort_seeders(mode, items)

            results = list(set(results + items[mode]))

        return results

    def _get_episode_search_strings(self, ep_obj, **kwargs):

        return generic.TorrentProvider._episode_strings(self, ep_obj, sep_date='|', **kwargs)


class FreshOnTVCache(tvcache.TVCache):

    def __init__(self, this_provider):
        tvcache.TVCache.__init__(self, this_provider)

        self.update_freq = 20

    def _cache_data(self):

        return self.provider.cache_data()


provider = FreshOnTVProvider()
