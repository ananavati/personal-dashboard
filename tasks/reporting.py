# coding: utf-8

from . import requires, utc_now, today_utc
from simplegauges import interpolators, postprocessors, aggregators
import datetime
from datetime import timedelta
import json
from azure.storage import BlobService


zero_fill_daily = lambda data: postprocessors.day_fill(data, 0)
zero_fill_weekly = lambda data: postprocessors.week_fill(data, 0)
monthly_max = lambda data: aggregators.monthly(data, max)
weekly_max = lambda data: aggregators.weekly(data, max)
weekly_min = lambda data: aggregators.weekly(data, min)
weekly_sum = lambda data: aggregators.weekly(data, sum)


@requires('azure.account', 'azure.key', 'azure.blob.container',
          'azure.blob.name')
def generate_and_upload(gauge_factory, config, logger):
    start = datetime.datetime.now()
    twitter_followers = gauge_factory('twitter.followers')
    twitter_tweets = gauge_factory('twitter.tweets')
    fb_friends = gauge_factory('facebook.friends')
    foursq_checkins = gauge_factory('foursquare.checkins')
    klout_score = gauge_factory('klout.score')
    runkeeper_activities = gauge_factory('runkeeper.activities')
    runkeeper_calories = gauge_factory('runkeeper.calories_burned')
    runkeeper_weight = gauge_factory('runkeeper.weight')
    atelog_coffees = gauge_factory('atelog.coffees')

    data = {}
    data_sources = [  # out name, gauge, days back, aggregator, postprocessors
        ('twitter.followers', twitter_followers, 30, None,
            [zero_fill_daily, interpolators.linear]),
        ('twitter.tweets', twitter_tweets, 30, None, [zero_fill_daily]),
        ('twitter.tweets', twitter_tweets, 30, None, [zero_fill_daily]),
        ('facebook.friends', fb_friends, 180, monthly_max, None),
        ('foursquare.checkins', foursq_checkins, 7, None, [zero_fill_daily]),
        ('klout.score', klout_score, 120, weekly_max, [zero_fill_weekly,
                                                       interpolators.linear]),
        ('runkeeper.calories', runkeeper_calories, 70, weekly_sum,
            [zero_fill_weekly]),
        ('runkeeper.activities', runkeeper_activities, 70, weekly_sum,
            [zero_fill_weekly]),
        ('runkeeper.weight', runkeeper_weight, 60, weekly_min,
            [zero_fill_weekly, interpolators.linear]),
        ('atelog.coffees', atelog_coffees, 14, None, [zero_fill_daily]),
    ]

    for ds in data_sources:
        data[ds[0]] = ds[1].aggregate(today_utc() - timedelta(days=ds[2]),
                                      aggregator=ds[3],
                                      post_processors=ds[4])

    report = {
        'generated': str(utc_now()),
        'data': data,
        'took': (datetime.datetime.now() - start).seconds
    }
    report_json = json.dumps(report, indent=4, default=json_date_serializer)

    blob_service = BlobService(config['azure.account'], config['azure.key'])
    blob_service.create_container(config['azure.blob.container'])
    blob_service.set_container_acl(config['azure.blob.container'],
                                   x_ms_blob_public_access='container')
    blob_service.put_blob(config['azure.blob.container'],
                          config['azure.blob.name'], report_json, 'BlockBlob')

    took = (datetime.datetime.now() - start).seconds
    logger.info('Report generated and uploaded. Took {0} s.'.format(took))


def json_date_serializer(obj):
    if isinstance(obj, datetime.datetime) or isinstance(obj, datetime.date):
        return str(obj)
    return obj
