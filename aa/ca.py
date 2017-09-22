import logging as log
from aa import data, utils
from aa.fetcher import Fetcher
import numpy
try:
    from xmlrpc.client import ServerProxy
except ImportError:  # Python 2 compatibility
    from xmlrpclib import ServerProxy


class CaClient(object):

    def __init__(self, url):
        self._proxy = ServerProxy(url)

    @staticmethod
    def _create_archive_event(pv, ca_event):
        value = ca_event['value']
        timestamp = ca_event['secs'] + 1e-9 * ca_event['nano']
        severity = ca_event['sevr']
        return data.ArchiveEvent(pv, value, timestamp, severity)

    def get(self, pv, start, end, count):
        start_secs = utils.datetime_to_epoch(start)
        end_secs = utils.datetime_to_epoch(end)
        response = self._proxy.archiver.values(1, [pv], start_secs, 0,
                                               end_secs, 0, count, 0)
        return [CaClient._create_archive_event(pv, val)
                for val in response[0]['values']]


class CaFetcher(Fetcher):

    def __init__(self, url):
        self._client = CaClient(url)

    def _get_values(self, pv, start, end=None, count=None):
        # Make count a large number if not specified to ensure we get all
        # data.
        count = 2**31 if count is None else count
        empty_array = numpy.zeros((0,))
        all_data = data.ArchiveData(pv, empty_array, empty_array, empty_array)
        last_timestamp = -1
        done = False
        while done is not True and len(all_data) < count:
            requested = min(count - len(all_data), 10000)
            if len(all_data.timestamps):
                last_timestamp = all_data.timestamps[-1]
                start = utils.epoch_to_datetime(last_timestamp)
            log.info('Request PV {} for {} samples.'.format(pv, requested))
            log.info('Request start {} end {}'.format(start, end))
            events = self._client.get(pv, start, end, requested)
            done = len(events) < requested
            # Drop any events that are earlier than ones already fetched.
            events = [e for e in events if e.timestamp > last_timestamp]
            new_data = data.data_from_events(pv, events)
            all_data.append(new_data)
        return all_data
