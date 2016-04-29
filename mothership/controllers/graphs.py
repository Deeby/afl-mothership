from flask import Blueprint, jsonify
from sqlalchemy.orm.attributes import InstrumentedAttribute

from mothership import models

graphs = Blueprint('graphs', __name__)


def trace(snapshots, property_name):
	try:
		start = snapshots[0].unix_time
	except IndexError:
		return {}
	x = []
	y = []
	for snapshot in snapshots:
		x.append(snapshot.unix_time*1000)
		y.append(getattr(snapshot, property_name))
	return {'x': x, 'y': y, 'type': 'scatter'}

@graphs.route('/graphs/campaign/<int:campaign_id>/<property_name>')
def graph_campaign(campaign_id, property_name):
	if not hasattr(models.FuzzerSnapshot, property_name) or not type(getattr(models.FuzzerSnapshot, property_name)) is InstrumentedAttribute:
		return 'Snapshot does not have property "%s"' % property_name, 400

	campaign = models.Campaign.get(id=campaign_id)
	return jsonify(
		data=[{
			**trace(fuzzer.snapshots, property_name),
			'name': fuzzer.name
		} for i, fuzzer in enumerate(campaign.fuzzers)],
		layout={
			'title': property_name.replace('_', ' '),
			'xaxis': {
				'type': 'date',
				'title': 'seconds'
			},
			'yaxis': {
				'title': property_name.replace('_', ' ')
			}
		}
	)


# @graphs.route('/graphs/campaign/execs/<campaign_id>')
# def execs(campaign_id):
# 	campaign = models.Campaign.get(id=campaign_id)
# 	return jsonify(
# 		data=[
# 			trace_sum(campaign.fuzzers, 'execs_per_sec')
# 		],
# 		layout={
# 			'title': 'Total Executions',
# 			'xaxis': {
# 				'title': 'time'
# 			},
# 			'yaxis': {
# 				'title': 'executions'
# 			}
# 		}
# 	)