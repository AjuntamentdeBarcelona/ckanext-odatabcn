import logging
import json

from ckan.plugins.toolkit import _
	
log = logging.getLogger(__name__)
	
# Require field if dataset visibility is public
def required_if_public(key, data, errors, context):
	value = data[key]
	private = data[('private',)]
	
	if private == 'False' and not value:
		errors[key].append(_('This field is required'))

# Historical information
def historical_yes_no(key, data, errors, context):
	value = data[key]
	tags = data[('tag',)]
	
	if ('Any' in tags):
		data[key] = 'Yes'
	else:
		data[key] = 'No'

	return data[key]
	
# Date Deactivation Informed
def date_deactivation_informed(key, data, errors, context):
	value = data[key]
	withdraw_date = data[('withdraw_date',)]
	
	if (withdraw_date):
		data[key] = 'Yes'
	else:
		data[key] = 'No'

	return data[key]