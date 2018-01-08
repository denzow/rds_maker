rds maker
==========================

thin wrapper boto3 for RDS

## install

```sh
$ pip install rdsmaker
```

## how to use

```python
from rds_maker import RdsMaker

# create connection instance
rds_maker = RdsMaker(
    region_name=REGION_NAME,
    az_name=AZ_NAME,
    aws_access_key=AWS_ACCESS_KEY,
    aws_rds_secret_key=AWS_RDS_SECRET_KEY,
    logger=default_logger
)

# get latest snapshot
snapshot_identifier = rds_maker.get_latest_snapshot(source_instance_name)
# create database from snapshot
rds_maker.create_db_instance_sync(
    db_identifier=target_instance_name,
    snapshot_identifier=snapshot_identifier,
    instance_class=instance_class,
)

# modify db parameters
rds_maker.change_db_instance_attributes_sync(db_identifier=target_instance_name, attributes={
    'DBParameterGroupName': DB_PARAMETER_GROUP,
    'BackupRetentionPeriod': 7,
    'VpcSecurityGroupIds': [VPC_SECURITY_GROUP_ID],
})

# rename database instance
rds_maker.rename_db_instance_sync(from_identifier=target_instance_name, to_identifier=renamed_instance_name)


```