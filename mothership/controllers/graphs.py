from collections import defaultdict

from flask import Blueprint, jsonify
from sqlalchemy import desc
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import InstrumentedAttribute

from mothership import models
from sqlalchemy import func

graphs = Blueprint('graphs', __name__)


# def trace(snapshots, property_name, starttime=None):
# 	try:
# 		start = snapshots[0].unix_time
# 	except IndexError:
# 		return {}
# 	if starttime:
# 		start = starttime
# 	x = []
# 	y = []
# 	for snapshot in snapshots:
# 		x.append((snapshot.unix_time-start)*1000)
# 		y.append(getattr(snapshot, property_name))
# 	return {'x': x, 'y': y}
# def crashes_at(fuzzer, time):
# 	q = models.Crash.query.filter(models.Crash.created < time).filter()
# 	print(q)
# 	return q.count()

def get_starts(fuzzers):
	"""
	Compute the list of start times for a list of fuzzers so that the series of

	fuzzers[n].snapshots[0...m].unix_time - get_starts(fuzzers)[n]

	does not include gaps when no fuzzers where running

	:param fuzzers: the list of fuzzers to compute the start times for
	:return: the list of start values
	"""
	run_times = [(f.start_time, f.snapshots.order_by(desc(models.FuzzerSnapshot.unix_time)).first().unix_time) for f in fuzzers]
	start, stop = run_times[0]
	starts = []
	for run_time, fuzzer in zip(run_times, fuzzers):
		n_start, n_stop = run_time
		if n_start > stop:
			start += n_start - stop
		stop = n_stop
		starts.append(start)
	return starts

def get_distinct(campaign, crash_filter={}):
	r = []
	fuzzers = [f for f in campaign.fuzzers.order_by(models.FuzzerInstance.start_time) if f.started]
	starts = dict(zip((f.id for f in fuzzers), get_starts(fuzzers)))
	crash_alias = aliased(models.Crash)
	sub = models.db_session.query(func.min(crash_alias.created)).filter(models.Crash.address == crash_alias.address)
	last_created, last_crashes, this_crashes = 0, 0, 0
	for crash in models.Crash.query\
			.filter(models.Crash.created == sub)\
			.filter_by(campaign_id=campaign.id, crash_in_debugger=True, **crash_filter)\
			.order_by(models.Crash.created)\
			.group_by(models.Crash.created, models.Crash.address):
		#c =
		created = (crash.created - starts[crash.instance_id]) * 1000
		if last_created == created:
			this_crashes += 1
		else:
			r.append([last_created, last_crashes])
			r.append([last_created+1, this_crashes])

			last_created, last_crashes, this_crashes = created, this_crashes, this_crashes+1
	r.append([(fuzzers[-1].last_update - starts[fuzzers[-1].id]) * 1000, last_crashes])
	return r


def graph(title, series):
	return jsonify(
		title={
			'text': title
		},
		series=[{
			'name': data[0],
			'data': data[1],
			'type': data[2] if data[2:] else 'line'
		} for data in series],
		xAxis={
			'type': 'datetime',
			'title': {
				'text': 'Duration'
			}
		},
		yAxis={
			'title': {
				'text': title
			}
		}
	)


@graphs.route('/graphs/campaign/<int:campaign_id>/address_heatmap')
def address_heatmap(campaign_id):
	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started:
		return jsonify()
	#start = get_starts(campaign.fuzzers)[0]
	crashes = defaultdict(int)
	addresses = set()
	#maxcrash = 0
	for crash in campaign.crashes.filter(models.Crash.address != None):
		#if crash.address > 100000000000000:
		#	continue
		#maxcrash = max(maxcrash, crash.address)
		addresses.add(crash.address)
		crashes[(crash.address, ((crash.created - crash.fuzzer.start_time) // (12*60*60)) )] += 1
	# crashes2 = defaultdict(int)
	# for (address, time), count in crashes.items():
	# 	crashes2[(address//20000, time)] += count
	# crashes = crashes2
	#crashes = {(k[0], )}
	return jsonify(
		chart= {
            'type': 'heatmap',
            # marginTop: 40,
            # marginBottom: 80,
            # plotBorderWidth: 1
        },
		colorAxis= {
            # 'stops': [
            #     [0, '#3060cf'],
            #     [0.5, '#fffbbc'],
            #     [0.9, '#c4463a'],
            #     [1, '#c4463a']
            # ],
            'min': 0,
            'max': 25,
			'minColor': '#0000FF',
            'maxColor': '#FF0000'
            # startOnTick: false,
            # endOnTick: false,
            # labels: {
            #     format: '{value}℃'
            # }
        },
		series= [{
			 'colsize': 1,
			'data': [
				[str(k[0]), k[1], v] for k, v in sorted(crashes.items())#, key=lambda x: x[0][::-1])
			]
		}],
		#yAxis= {
        #    'type': 'datetime',
            # 'min': 0,
            # 'max': 24*60*60*1000,
		#},
		xAxis= {
			#'tickLength': 500
			'categories': [str(x) for x in sorted(addresses)],

		# 	'min': 0,
		# 	'max': 100
		}
	)


@graphs.route('/graphs/campaign/<int:campaign_id>/distinct_addresses')
def graph_campaign_addresses(campaign_id):
	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started:
		return jsonify()
	return graph('Distinct Addresses', [
		('All Crashes', get_distinct(campaign))
	])


@graphs.route('/graphs/campaign/<int:campaign_id>/<property_name>')
def graph_campaign(campaign_id, property_name):
	if not hasattr(models.FuzzerSnapshot, property_name) or not type(getattr(models.FuzzerSnapshot, property_name)) is InstrumentedAttribute:
		return 'Snapshot does not have property "%s"' % property_name, 400

	campaign = models.Campaign.get(id=campaign_id)
	if not campaign.started:
		return jsonify()

	fuzzers = [f for f in campaign.fuzzers.order_by(models.FuzzerInstance.start_time) if f.started]
	return graph(property_name.replace('_', ' ').title(), [(
		fuzzer.name,
		[[
			(snapshot.unix_time - start) * 1000,
			getattr(snapshot, property_name)
		] for snapshot in fuzzer.snapshots]
	) for start, fuzzer in zip(get_starts(fuzzers), fuzzers)])