# -*- coding: utf-8 -*-
"""Elasticsearch functionality"""

import json
from collections import Counter
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.client import indices

from django.conf import settings

from texcavator import utils

_ES_RETURN_FIELDS = ('article_dc_title',
                     'paper_dcterms_temporal',
                     'paper_dcterms_spatial',
                     'paper_dc_title',
                     'paper_dc_date')

_KB_DISTRIBUTION_VALUES = {'sd_national': 'Landelijk',
                           'sd_regional': 'Regionaal/lokaal',
                           'sd_antilles': 'Nederlandse Antillen',
                           'sd_surinam': 'Suriname',
                           'sd_indonesia': 'Nederlands-Indië / Indonesië'}

_KB_ARTICLE_TYPE_VALUES = {'st_article': 'artikel',
                           'st_advert': 'advertentie',
                           'st_illust': 'illustratie met onderschrift',
                           'st_family': 'familiebericht'}

_DOCUMENT_TEXT_FIELD = 'text_content'
_DOCUMENT_TITLE_FIELD = 'article_dc_title'
_AGG_FIELD = _DOCUMENT_TEXT_FIELD


def _es():
    """Returns ElasticSearch instance."""
    return Elasticsearch(settings.ELASTICSEARCH_HOST + ":" +
                         str(settings.ELASTICSEARCH_PORT))


def do_search(idx, typ, query, start, num, date_range, exclude_distributions,
              exclude_article_types, return_source=False):
    """Returns ElasticSearch search results.

    Fetch all documents matching the query and return a list of
    elasticsearch results.

    This method accepts boolean queries in the Elasticsearch query string
    syntax (see Elasticsearch reference).

    Parameters
    ----------
    idx : str
        The name of the elasticsearch index
    typ : str
        The type of document requested
    query : str
        A query string in the Elasticsearch query string language
    start : int
        An integer representing the index of the first result to be retrieved
    num : int
        The total number of results to be retrieved
    date_range : dict
        A dictionary containg the upper and lower dates of the
        requested date range
    exclude_distributions : list
        A list of strings respresenting distributions that should be excluded
        from the search
    exclude_article_types : list
        A list of strings representing article types that should be excluded
        from the search
    return_source : boolean, optional
        A boolean indicating whether the _source of ES documents should be
        returned or a smaller selection of document fields. The smaller set of
        document fields (stored in _ES_RETURN_FIELDS) is the default

    Returns
    -------
    validity : boolean
        A boolean indicating whether the input query string is valid.
    results : list
        A list of elasticsearch results or a message explaining why the input
        query string is invalid.
    """
    q = create_query(query, date_range, exclude_distributions,
                     exclude_article_types)

    valid_q = indices.IndicesClient(_es()).validate_query(index=idx,
                                                          doc_type=typ,
                                                          body=q,
                                                          explain=True)

    if valid_q.get('valid'):
        if return_source:
            # for each document return the _source field that contains all
            # document fields (no fields parameter in the ES call)
            return True, _es().search(index=idx, doc_type=typ, body=q,
                                      from_=start, size=num)
        else:
            # for each document return the fields listed in_ES_RETURN_FIELDS
            return True, _es().search(index=idx, doc_type=typ, body=q,
                                      fields=_ES_RETURN_FIELDS, from_=start,
                                      size=num)
    return False, valid_q.get('explanations')[0].get('error')


def count_search_results(idx, typ, query, date_range, exclude_distributions,
                         exclude_article_types):
    """Count the number of results for a query
    """
    q = create_query(query, date_range, exclude_distributions,
                     exclude_article_types)

    return _es().count(index=idx, doc_type=typ, body=q)


def get_document(idx, typ, doc_id):
    """Return a document given its id.

    Parameters
    ----------
    idx : str
        The name of the elasticsearch index
    typ : str
        The type of document requested
    doc_id : str
        The id of the document to be retrieved
    """
    try:
        result = _es().get(index=idx, doc_type=typ, id=doc_id)
    except:
        return None

    return result['_source']


def create_query(query_str, date_range, exclude_distributions,
                 exclude_article_types):
    """Create elasticsearch query from input string.

    This method accepts boolean queries in the Elasticsearch query string
    syntax (see Elasticsearch reference).

    Returns a dict that represents the query in the elasticsearch query DSL.
    """

    filter_must_not = []
    for ds in exclude_distributions:
        filter_must_not.append(
            {"term": {"paper_dcterms_spatial": _KB_DISTRIBUTION_VALUES[ds]}})

    for typ in exclude_article_types:
        filter_must_not.append(
            {"term": {"article_dc_subject": _KB_ARTICLE_TYPE_VALUES[typ]}})

    query = {
        'query': {
            'filtered': {
                'query': {
                    'query_string': {
                        'query': query_str
                    }
                },
                'filter': {
                    'bool': {
                        'must': [
                            {
                                'range': {
                                    'paper_dc_date': {
                                        'gte': date_range['lower'],
                                        'lte': date_range['upper']
                                    }
                                }
                            }
                        ],
                        'must_not': filter_must_not
                    }
                }
            }
        }
    }

    return query


def create_ids_query(ids):
    """Returns an Elasticsearch ids query.

    Create Elasticsearch query that returns documents based on a list of
    ids.

    Parameters
    ----------
    ids : list
        A list containing document ids

    Returns
    -------
    query : dict
        A dictionary representing an ES ids query
    """
    query = {
        'query': {
            'filtered': {
                'filter': {
                    'ids': {
                        'type': settings.ES_DOCTYPE,
                        'values': ids
                    }
                }
            }
        }
    }

    return query


def create_day_statistics_query(date_range, agg_name):
    """Create ES query to gather day statistics for the given date range.

    This function is used by the gatherstatistics management command.
    """
    date_lower = datetime.strptime(date_range['lower'], '%Y-%m-%d').date()
    date_upper = datetime.strptime(date_range['upper'], '%Y-%m-%d').date()
    diff = date_upper-date_lower
    num_days = diff.days

    return {
        'query': {
            'filtered': {
                'filter': {
                    'bool': {
                        'must': [
                            {
                                'range': {
                                    'paper_dc_date': {
                                        'gte': date_range['lower'],
                                        'lte': date_range['upper']
                                    }
                                }
                            }
                        ]
                    }
                },
                'query': {
                    'match_all': {}
                }
            }
        },
        'aggs': {
            agg_name: {
                'terms': {
                    'field': 'paper_dc_date',
                    'size': num_days
                }
            }
        },
        'size': 0
    }


def word_cloud_aggregation(agg_name, num_words=100):
    """Return aggragation part of terms aggregation (=word cloud) that can be
    added to any Elasticsearch query."""
    agg = {
        agg_name: {
            'terms': {
                'field': _AGG_FIELD,
                'size': num_words
            }
        }
    }

    return agg


def single_document_word_cloud(idx, typ, doc_id, min_length=0, stopwords=None):
    """Return data required to draw a word cloud for a single document.


    Parameters
    ----------
    idx : str
        The name of the elasticsearch index
    typ : str
        The type of document requested
    doc_id : str
        The id of the document the word cloud should be created for
    min_length : int, optional
        The minimum length of words in the word cloud
    stopwords : list, optional
        A list of words that should be removed from the word cloud

    Returns
    -------
    dict : dict
        A dictionary that contains word frequencies for all the terms in The
        document. The data returned is formatted according to what is expected
        by the user interface:
        {
            'status': 'ok'
            'max_count': ...
            'result':
                [
                    {
                        'term': ...
                        'count': ...
                    },
                    ...
                ]
        }
    """

    if not doc_id:
        return {
            'status': 'error',
            'error': 'No document id provided.'
        }

    bdy = {
        'fields': [_DOCUMENT_TEXT_FIELD, _DOCUMENT_TITLE_FIELD]
    }
    t_vector = _es().termvector(index=idx, doc_type=typ, id=doc_id, body=bdy)

    if not stopwords:
        stopwords = []

    if t_vector.get('found', False):
        wordcloud = Counter()
        for field, data in t_vector.get('term_vectors').iteritems():
            for term, count_dict in data.get('terms').iteritems():
                if term not in stopwords and len(term) >= min_length:
                    wordcloud[term] += int(count_dict.get('term_freq'))

        common_terms = wordcloud.most_common(100)
        result = [{'term': t, 'count': c} for t, c in common_terms]

        return {
            'max_count': common_terms[0][0],
            'result': result,
            'status': 'ok'
        }

    return {
        'status': 'error',
        'error': 'Document with id "{}" could not be found.'.format(doc_id)
    }


def multiple_document_word_cloud(idx, typ, query, date_range, dist, art_types,
                                 ids=None):
    """Return data required to draw a word cloud for multiple documents

    This function generates word cloud data using terms aggregations in ES.
    However, for newspaper articles this approach is not feasible; ES runs out
    of memory very quickly. Therefore, another approach to generating word
    cloud data was added: termvector_word_cloud

    See also
    --------
    single_document_word_cloud() generate data for a single document word cloud
    termvector_word_cloud() generate word cloud data using termvector approach
    """
    if not ids:
        ids = []

    agg_name = 'words'

    # word cloud based on query
    if query:
        q = create_query(query, date_range, dist, art_types)
        q['aggs'] = word_cloud_aggregation(agg_name)
    # word cloud based on document ids
    elif not query and len(ids) > 0:
        q = create_ids_query(ids)
        q['aggs'] = word_cloud_aggregation(agg_name)
    else:
        return {
            'status': 'error',
            'error': 'No valid query provided for word cloud generation.'
        }

    aggr = _es().search(index=idx, doc_type=typ, body=q, size=0)

    aggr_result_list = aggr.get('aggregations').get(agg_name).get('buckets')
    max_count = aggr_result_list[0].get('doc_count')

    result = []
    for term in aggr_result_list:
        result.append({
            'term': term.get('key'),
            'count': term.get('doc_count')
        })

    return {
        'max_count': max_count,
        'result': result,
        'status': 'ok',
        'took': aggr.get('took', 0)
    }


def termvector_word_cloud(idx, typ, doc_ids, burst, min_length=0,
                          stopwords=None, chunk_size=1000):
    """Generate word cloud data using the termvector approach

    Return data required to draw a word cloud for multiple documents by
    'manually' merging termvectors.

    See also
    --------
    single_document_word_cloud() generate data for a single document word cloud
    multiple_document_word_cloud() generate word cloud data using terms
    aggregation approach
    """

    wordcloud = Counter()

    for ids in utils.chunks(doc_ids, chunk_size):
        bdy = {
            'ids': ids,
            'parameters': {
                'fields': [_DOCUMENT_TEXT_FIELD, _DOCUMENT_TITLE_FIELD],
                'term_statistics': False,
                'field_statistics': False,
                'offsets': False,
                'payloads': False,
                'positions': False
            }
        }

        t_vectors = _es().mtermvectors(index='kb', doc_type='doc', body=bdy)

        for doc in t_vectors.get('docs'):
            for field, data in doc.get('term_vectors').iteritems():
                temp = {}
                for term, details in data.get('terms').iteritems():
                    if len(term) >= min_length:
                        temp[term] = int(details['term_freq'])
                wordcloud.update(temp)

    if not stopwords:
        stopwords = []
    for stopw in stopwords:
        del wordcloud[stopw]

    result = []
    for term, count in wordcloud.most_common(100):
        result.append({
            'term': term,
            'count': count
        })

    return {
        'max_count': wordcloud.most_common(1)[0][1],
        'result': result,
        'status': 'ok',
        'burstcloud': burst
    }


def get_search_parameters(req_dict):
    """Return a tuple of search parameters extracted from a dictionary

    Parameters
    ----------
    req_dict : dict
        A Django request dictionary

    Returns
    -------
    dict : dict
        A dictionary that contains query metadata
    """
    query_str = req_dict.get('query', None)

    start = int(req_dict.get('startRecord', 1))

    result_size = int(req_dict.get('maximumRecords', 20))

    date_range_str = req_dict.get('dateRange', settings.TEXCAVATOR_DATE_RANGE)
    dates = daterange2dates(date_range_str)

    distributions = []
    for ds in _KB_DISTRIBUTION_VALUES.keys():
        use_ds = json.loads(req_dict.get(ds, "true"))
        if not use_ds:
            distributions.append(ds)

    article_types = []
    for typ in _KB_ARTICLE_TYPE_VALUES:
        use_type = json.loads(req_dict.get(typ, "true"))
        if not use_type:
            article_types.append(typ)

    collection = req_dict.get('collection', settings.ES_INDEX)

    return {
        'query': query_str,
        'start': start,
        'result_size': result_size,
        'dates': dates,
        'distributions': distributions,
        'article_types': article_types,
        'collection': collection
    }


def daterange2dates(date_range_str):
    """Return a dictionary containing the date boundaries specified.

    If the input string does not specify two dates, the maximum date range is
    retrieved from the settings.
    """
    dates_str = date_range_str.split(',')
    if not len(dates_str) == 2:
        return daterange2dates(settings.TEXCAVATOR_DATE_RANGE)

    dates = [str(datetime.strptime(date, '%Y%m%d').date())
             for date in dates_str]
    return {'lower': min(dates), 'upper': max(dates)}


def get_document_ids(idx, typ, query, date_range, exclude_distributions=[],
                     exclude_article_types=[]):
    """Return a list of document ids and dates for a query
    """
    doc_ids = []

    q = create_query(query, date_range, exclude_distributions,
                     exclude_article_types)

    date_field = 'paper_dc_date'
    fields = [date_field]
    get_more_docs = True
    start = 0
    num = 2500

    while get_more_docs:
        results = _es().search(index=idx, doc_type=typ, body=q, fields=fields,
                               from_=start, size=num)
        for result in results['hits']['hits']:
            doc_ids.append(
                {
                    'identifier': result['_id'],
                    'date': datetime.strptime(result['fields'][date_field][0],
                                              '%Y-%m-%d').date()
                })

        start = start + num

        if len(results['hits']['hits']) < num:
            get_more_docs = False

    return doc_ids


def day_statistics(idx, typ, date_range, agg_name):
    """Gather day statistics for all dates in the date range

    This function is used by the gatherstatistics management command.
    """
    q = create_day_statistics_query(date_range, agg_name)

    results = _es().search(index=idx, doc_type=typ, body=q, size=0)

    if 'took' in results:
        return results
    return None
