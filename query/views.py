# -*- coding: utf-8 -*-
import os
import json
import logging
import csv
from sys import stderr
from datetime import datetime
from urllib import quote_plus, unquote_plus
from urlparse import urljoin

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.core.validators import validate_email
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.servers.basehttp import FileWrapper
from django.conf import settings
from django.db.models import Q, Min, Max
from django.db import IntegrityError

from .models import Distribution, ArticleType, Query, DayStatistic, \
    StopWord, Pillar, Newspaper, Period
from .utils import query2docidsdate
from .burstsdetector import bursts
from .download import create_zipname, execute
from services.es import get_search_parameters, count_search_results
from texcavator.utils import json_response_message

logger = logging.getLogger(__name__)


@login_required
def index(request):
    """Returns the list of Queries for the current User."""
    queries = Query.objects.filter(user=request.user).order_by('-date_created')
    queries_json = [q.get_query_dict() for q in queries]
    return json_response_message('OK', '', {'queries': queries_json})


@login_required
def query(request, query_id):
    """Returns a single Query, checks if Query belongs to User."""
    query = get_object_or_404(Query, pk=query_id)
    if not request.user == query.user:
        return json_response_message('ERROR', 'Query does not belong to user.')
    return json_response_message('OK', '', {'query': query.get_query_dict()})


@csrf_exempt
@login_required
def create_query(request):
    """Creates a new query."""
    params = get_search_parameters(request.POST)
    title = request.POST.get('title')
    comment = request.POST.get('comment')

    try:
        q = Query(query=params['query'],
                  title=title,
                  comment=comment,
                  user=request.user)
        q.save()

        for date_range in params['dates']:
            date_lower = datetime.strptime(date_range['lower'], '%Y-%m-%d')
            date_upper = datetime.strptime(date_range['upper'], '%Y-%m-%d')
            p = Period(query=q, date_lower=date_lower, date_upper=date_upper)
            p.save()

        for distr in Distribution.objects.all():
            if distr.id in params['distributions']:
                q.exclude_distributions.add(distr)

        for art_type in ArticleType.objects.all():
            if art_type.id in params['article_types']:
                q.exclude_article_types.add(art_type)

        for pillar in Pillar.objects.all():
            if pillar.id in params['pillars']:
                q.selected_pillars.add(pillar)
    except IntegrityError as _:
        return json_response_message('ERROR', 'A query with this title already exists.')
    except Exception as e:
        return json_response_message('ERROR', str(e))

    return json_response_message('SUCCESS', '')


@csrf_exempt
@login_required
def delete(request, query_id):
    """Deletes a query.
    """
    query = Query.objects.get(pk=query_id)
    if not query:
        return json_response_message('ERROR', 'Query not found.')

    if not request.user == query.user:
        return json_response_message('ERROR', 'Query does not belong to user.')

    q = query.title
    query.delete()

    return json_response_message('SUCCESS', 'Query "{}" deleted.'.format(q))


@csrf_exempt
@login_required
def update(request, query_id):
    """Updates a query.
    """
    query = Query.objects.get(pk=query_id)

    if not query:
        return json_response_message('ERROR', 'Query not found.')

    if not request.user == query.user:
        return json_response_message('ERROR', 'Query does not belong to user.')

    params = get_search_parameters(request.POST)
    title = request.POST.get('title')
    comment = request.POST.get('comment')

    try:
        Query.objects.filter(pk=query_id).update(query=params['query'],
                                                 title=title,
                                                 comment=comment)

        Period.objects.filter(query__pk=query_id).delete()
        for date_range in params['dates']:
            date_lower = datetime.strptime(date_range['lower'], '%Y-%m-%d')
            date_upper = datetime.strptime(date_range['upper'], '%Y-%m-%d')
            p = Period(query=query, date_lower=date_lower, date_upper=date_upper)
            p.save()

        query.exclude_distributions.clear()
        for distr in Distribution.objects.all():
            if distr.id in params['distributions']:
                query.exclude_distributions.add(distr)

        query.exclude_article_types.clear()
        for art_type in ArticleType.objects.all():
            if art_type.id in params['article_types']:
                query.exclude_article_types.add(art_type)

        query.selected_pillars.clear()
        for pillar in Pillar.objects.all():
            if pillar.id in params['pillars']:
                query.selected_pillars.add(pillar)
    except Exception as e:
        return json_response_message('ERROR', str(e))

    return json_response_message('SUCCESS', 'Query saved.')


@login_required
def timeline(request, query_id, resolution):
    """
    Generates a timeline for a query.
    TODO: the timeline view should be moved to a separate app
    """
    logger.info('query/timeline/ - user: {}'.format(request.user.username))

    if settings.DEBUG:
        print >> stderr, "query/bursts() query_id:", query_id, \
                         "resolution:", resolution

    normalize = request.REQUEST.get('normalize') == 1
    bg_smooth = False

    query = get_object_or_404(Query, pk=query_id)

    # Retrieve the min/max date
    periods = Period.objects.filter(query=query)
    _, begindate = periods.aggregate(Min('date_lower')).popitem()
    _, enddate = periods.aggregate(Max('date_upper')).popitem()

    # normalization and/or smoothing
    values = DayStatistic.objects.values('date', 'count').all()
    date2countC = {}
    for dc in values:
        if enddate >= dc['date'] >= begindate:
            date2countC[dc['date']] = dc['count']

    documents_raw = query2docidsdate(query,
                                     str(begindate),
                                     str(enddate))
    documents = sorted(documents_raw, key=lambda k: k["date"])
    doc2date = {}
    for doc in documents:
        doc_date = doc["date"]
        if enddate >= doc_date >= begindate:
            doc2date[doc["identifier"]] = doc_date

    if settings.DEBUG:
        print >> stderr, "burst parameters:"
        # print >> stderr, "len doc2date:", len(doc2date)  # can be big
        print >> stderr, "(doc2date not shown)"
        print >> stderr, "doc2relevance: {}"
        # print >> stderr, "len date2countC:", len(date2countC)  # can be big
        print >> stderr, "(date2countC not shown)"
        print >> stderr, "normalize:", normalize
        print >> stderr, "bg_smooth:", False
        print >> stderr, "resolution:", resolution

    bursts_list = bursts.bursts(doc2date,
                                {},
                                date2countC=date2countC,
                                normalise=normalize,
                                bg_smooth=bg_smooth,
                                resolution=resolution)[0]

    date2count = {}
    for date, tup in bursts_list.iteritems():
        doc_float, zero_one, i, limit, doc_count, doc_ids = tup
        if doc_count != 0:
            doc_float = float("%.1f" % doc_float)  # less decimals
            if limit:                              # not None
                limit = float("%.1f" % limit)      # less decimals
            date2count[str(date)] = (doc_float,
                                     zero_one,
                                     i,
                                     limit,
                                     doc_count,
                                     doc_ids)

    return HttpResponse(json.dumps(date2count))


@csrf_exempt
@login_required
def add_stopword(request):
    """Adds a stopword to the stopword list.
    """
    query_id = request.POST.get('query_id')
    word = request.POST.get('stopword')

    q = None

    try:
        q = Query.objects.get(pk=query_id)
    except Query.DoesNotExist:
        pass
    except Exception as e:
        return json_response_message('ERROR', str(e))

    StopWord.objects.get_or_create(user=request.user, query=q, word=word)

    return json_response_message('SUCCESS', 'Stopword added.')


@csrf_exempt
@login_required
def delete_stopword(request, stopword_id):
    """Deletes a stopword from the stopword list.
    """
    stopword = StopWord.objects.get(pk=stopword_id)
    if not stopword:
        return json_response_message('ERROR', 'Stopword not found.')

    if not request.user == stopword.user:
        return json_response_message('ERROR', 'Stopword does not belong to '
                                              'user.')
    stopword.delete()

    return json_response_message('SUCCESS', 'Stopword deleted.')


# TODO: turn into get method (get user via currently logged in user)
@csrf_exempt
@login_required
def stopwords(request):
    """Returns the stopword list for a user and query.
    """
    stopwords = StopWord.objects.select_related().filter(user=request.user) \
                                .order_by('word').order_by('query')

    stopwordlist = []
    for word in stopwords:
        stopwordlist.append(word.get_stopword_dict())

    params = {
        'stopwords': stopwordlist,
        'editglob': False
    }

    return json_response_message('SUCCESS', '', params)


@csrf_exempt
@login_required
def export_stopwords(request):
    """Exports all stopwords for the current user to a .csv-file
    """
    sw = StopWord.objects.filter(Q(user=request.user) | Q(user=None)).order_by('word')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stopwords.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['word', 'user', 'query'])

    for stopword in sw:
        u = stopword.user.username if stopword.user else '(all)'
        q = stopword.query if stopword.query else '(all)'
        writer.writerow([stopword.word.encode('utf-8'), u, q])

    return response


@csrf_exempt
@login_required
def download_prepare(request):
    """Prepares the ocr+meta-data zipfile for download
    """
    if settings.DEBUG:
        print >> stderr, "download_prepare()"
        print >> stderr, request.REQUEST
    logger.info('query/download/prepare - user: {}'.
                format(request.user.username))

    user = request.user
    query = Query.objects.get(title=request.GET.get('query_title'), user=user)

    params = query.get_query_dict()
    result = count_search_results(settings.ES_INDEX,
                                  settings.ES_DOCTYPE,
                                  params['query'],
                                  params['dates'],
                                  params['exclude_distributions'],
                                  params['exclude_article_types'],
                                  params['selected_pillars'])
    count = result.get('count')

    if count > settings.QUERY_DATA_MAX_RESULTS:
        msg = "Your query has too much results to export: " + str(count)
        msg += " where " + str(settings.QUERY_DATA_MAX_RESULTS) + " are allowed. "
        msg += "Please consider filtering your results before exporting."
        return json_response_message('error', msg)

    if user.email == "":
        msg = "Preparing your download for query <br/><b>" + query.title + \
              "</b> failed.<br/>A valid email address is needed for user " \
              "<br/><b>" + user.username + "</b>"
        if settings.DEBUG:
            print >> stderr, msg
        return json_response_message('error', msg)

    try:
        validate_email(user.email)
    except:
        msg = "Preparing your download for query <br/><b>" + query.title + \
              "</b> failed.<br/>The email address of user <b>" + \
              user.username + "</b> could not be validated: <b>" + \
              user.email + "</b>"
        if settings.DEBUG:
            print >> stderr, msg
        return json_response_message('error', msg)

    zip_basename = create_zipname(user, query)
    url = urljoin('http://{}'.format(request.get_host()),
                  "/query/download/" + quote_plus(zip_basename))
    email_message = "Texcavator query: " + query.title + "\n" + zip_basename + \
        "\nURL: " + url
    if settings.DEBUG:
        print >> stderr, email_message
        print >> stderr, 'http://{}'.format(request.get_host())

    # zip documents by celery background task
    execute(query, dict(request.REQUEST), zip_basename, user.email, email_message)

    msg = "Your export for query <b>" + query.title + \
          "</b> is completed.<br/>An e-mail with a download link has been sent " + \
          "to <b>" + user.email + "</b>."
    return json_response_message('SUCCESS', msg)


@csrf_exempt
@login_required
def download_data(request, zip_name):
    """Downloads the prepared data created from :func:`views.download_prepare` above

    Parameters:
        request: the default Django request
        zip_name: the name of the zip to be downloaded

    Returns:
        A HTTPResponse that will allow downloading of the zip file.
    """
    msg = "download_data() zip_basename: %s" % zip_name
    if settings.DEBUG:
        print >> stderr, msg
    logger.info('query/download/{} - user: {}'.format(zip_name,
                                                      request.user.username))
    # TODO: use mod_xsendfile
    zip_basedir = os.path.join(settings.PROJECT_PARENT,
                               settings.QUERY_DATA_DOWNLOAD_PATH)
    zip_filename = unquote_plus(zip_name) + ".zip"
    zip_pathname = os.path.join(zip_basedir, zip_filename)

    wrapper = FileWrapper(open(zip_pathname, 'rb'))
    response = HttpResponse(wrapper, content_type='application/zip')
    response['Content-Length'] = os.path.getsize(zip_pathname)
    response['Content-Disposition'] = "attachment; filename=%s" % zip_filename

    return response


@login_required
def retrieve_pillars(request):
    """Retrieves all Pillars as JSON objects
    """
    pillars = Pillar.objects.all()
    return json_response_message('ok', '', {'result': [{'id': p.id, 'name': p.name} for p in pillars]})


@login_required
def export_newspapers(request):
    """Exports all Newspapers to a .csv-file
    """
    newspapers = Newspaper.objects.all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="newspapers.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['id', 'title', 'start date', 'end date', 'editions', 'pillar'])

    for n in newspapers:
        pillar = n.pillar.name if n.pillar else ''
        writer.writerow([n.id, n.title.encode('utf-8'), n.start_date, n.end_date, n.editions, pillar])

    return response
