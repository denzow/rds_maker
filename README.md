rds maker
==========================

thin wrapper boto3 for RDS


```python
from rds_maker import RdsMaker


rds_maker = RdsMaker(
    region_name=REGION_NAME,
    az_name=AZ_NAME,
    aws_access_key=AWS_ACCESS_KEY,
    aws_rds_secret_key=AWS_RDS_SECRET_KEY,
    logger=default_logger
)

# 最新のスナップショット識別子取得
snapshot_identifier = rds_maker.get_latest_snapshot(source_instance_name)
# DB作成
rds_maker.create_db_instance_sync(
    db_identifier=target_instance_name,
    snapshot_identifier=snapshot_identifier,
    instance_class=instance_class,
)

# 作成時には設定できない部分を変更
rds_maker.change_db_instance_attributes_sync(db_identifier=target_instance_name, attributes={
    'DBParameterGroupName': DB_PARAMETER_GROUP,
    'BackupRetentionPeriod': 7,
    'VpcSecurityGroupIds': [VPC_SECURITY_GROUP_ID],
})

# インスタンスをリネーム
rds_maker.rename_db_instance_sync(from_identifier=target_instance_name, to_identifier=renamed_instance_name)


```