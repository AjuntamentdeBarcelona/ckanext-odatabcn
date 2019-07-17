from ckan.model import meta, domain_object
from sqlalchemy import types, Column, Table

tracking_raw_table = Table('tracking_raw', meta.metadata,
        Column('user_key', types.Unicode(100), nullable=False, primary_key=True),
        Column('url', types.UnicodeText, nullable=False, primary_key=True),
        Column('tracking_type', types.Unicode(10), nullable=False),
        Column('access_timestamp', types.DateTime, primary_key=True),
        extend_existing=True
    )

class TrackingRaw(domain_object.DomainObject):
    pass

meta.mapper(TrackingRaw, tracking_raw_table)