# -*- coding: utf-8 -*-

""" Old ElasticSearch BiLand functionality.

This module must be removed.
"""

from sys import stderr
from lxml import etree
from lxml.html import fromstring

from django.conf import settings

ES_CHUNK_SIZE = 2000


def elasticsearch_htmlresp(collection, start_record, chunk_size, es_dict):
    """Create HTML response from ElasticSearch request.

    Parameters:
        collection : str
            The collection search results have been retrieved from. For
            Texcavator the collection is the ElasticSearch index name.
        start_record : int
            Search results are returned as a numbered list. The start record is
            the number this list should start with (pagination).
        chunk_size : int
            The number of results displayed.
        es_dict : dictionary
            Dictionary returned by ElasticSearch for a search request (contains
            the returned documents).

    Returns:
        string : str
            The html string for displaying the search results.
    """
    if settings.DEBUG:
        print >> stderr, "elasticsearch_htmlresp()"

    hits = es_dict["hits"]
    hits_total = hits["total"]
    hits_max_score = hits["max_score"]
    hits_list = hits["hits"]
    hits_retrieved = len(hits_list)

    html_str = '<head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"></head>'
    html_str += '<body>'
    if hits_retrieved != hits_total:  # did not get everything
        if start_record > 1:
            have_prev = True
        else:
            have_prev = False

        if start_record + chunk_size < hits_total:
            have_next = True
        else:
            have_next = False

        href_pref = '<a href="javascript:nextResults(-' + str( chunk_size ) + ');">previous</a>'
        href_next = '<a href="javascript:nextResults(+' + str( chunk_size ) + ');">next</a>'

        html_str += '<span style="float:right">'
        if have_prev and have_next:
            html_str = html_str + href_pref + ' | ' + href_next
        elif have_prev:
            html_str = html_str + href_pref
        elif have_next:
            html_str = html_str + href_next
        html_str += '</span>'

    if hits_total == 0 or not hits_max_score:
        html_str += '<p>Found ' + "%s" % hits_total + ' records.'
    else:
        html_str += '<p>Found ' + "%s" % hits_total + ' records, '
        html_str += 'max score = ' + "%1.2f" % hits_max_score + '.</p>'

    html_str += '<ol start="' + '%s' % start_record + '">'

    datastore = "DSTORE_ELASTICSEARCH"

    for h in range(hits_retrieved):
        hit = hits_list[h]

        _id = hit["_id"]
        _score = hit["_score"]

        if collection == settings.ES_INDEX:
            article_dc_title = hit["fields"]["article_dc_title"][0]
            paper_dcterms_temporal = hit["fields"]["paper_dcterms_temporal"][0]
            paper_dcterms_spatial = hit["fields"]["paper_dcterms_spatial"][0]
        else:
            try:
                article_dc_title = hit["fields"]["article_dc_title"][0]
            except:
                article_dc_title = ""
            paper_dcterms_temporal = ""
            paper_dcterms_spatial = ""

        try:
            zipfile = hit["fields"]["zipfile"][0]
        except:
            zipfile = ""

        paper_dc_title = hit["fields"]["paper_dc_title"][0]
        paper_dc_date = hit["fields"]["paper_dc_date"][0]

        item_str = "<li>"
        item_str += '<a href=javascript:retrieveRecord("' + datastore + '","' + collection + '","' + _id + '","' + zipfile + '"); '

        if len(article_dc_title) > 45:  # limit displayed title length
            item_str += 'title=' + article_dc_title + '><b>' + article_dc_title[0:45] + '</b>...</a>'
        else:
            item_str += 'title=' + article_dc_title + '><b>' + article_dc_title + '</b></a>'

        item_str += '<br>' + paper_dc_title
        item_str += '<br>' + paper_dc_date

        if paper_dcterms_temporal != "":
            item_str += ', ' + paper_dcterms_temporal
        if paper_dcterms_spatial != "":
            item_str += ', ' + paper_dcterms_spatial

        if _score:
            item_str += ' [score: '
            item_str += "%1.2f" % _score
            item_str += ']'

        item_str += "</li>"
        html_str += item_str

    html_str += '</ol></body>'

    html = fromstring(html_str)
    html_str = etree.tostring(html, pretty_print=True)

    return html_str
