# coding: utf-8

import os
import sys
import argparse
import datetime

from logging import getLogger, Formatter, StreamHandler, DEBUG
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + os.sep + '../')

from rds_maker import RdsMaker

# logger
default_logger = getLogger(__name__)
formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = StreamHandler()
handler.setLevel(DEBUG)
handler.setFormatter(formatter)
default_logger.setLevel(DEBUG)
default_logger.addHandler(handler)


# need rds full control account.
AWS_ACCESS_KEY = os.environ.get('AWS_RDS_KEY')
AWS_RDS_SECRET_KEY = os.environ.get('AWS_RDS_SECRET_KEY')

REGION_NAME = os.environ.get('AWS_RDS_REGION_NAME')
AZ_NAME = os.environ.get('AWS_RDS_AZ_NAME')
DB_PARAMETER_GROUP = os.environ.get('AWS_RDS_DB_PARAMETER_GROUP')
VPC_SECURITY_GROUP_ID = os.environ.get('AWS_RDS_VPC_SECURITY_GROUP_ID')


COMMAND_DESCRIPTION = """
remake_rds.py
=================
指定したスナップショットをもとに任意のRDSを(再)作成します。
usage example:

### 再作成モード
> python {file_name} -s source-db-identifier -t target-db-identifier -c db.t2.small

* source-db-identifierの最新のスナップショットから
* 既存のtarget-db-identifierを削除し
* 新しくtarget-db-identifierとして
* db.t2.smallで作成する

### 作成モード
> python {file_name} --only-create -s source-db-identifier -t target-db-identifier -c db.t2.small

* source-db-identifierの最新のスナップショットから
* 新しくtarget-db-identifierとして
* db.t2.smallで作成する

""".format(file_name=__file__)


def init():
    """
    引数処理
    :return: ソースインスタンス名, 再作成対象インスタンス名, インスタンスサイズ
    :rtype: tuple(str, str, str)
    """
    parser = argparse.ArgumentParser(description=COMMAND_DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '-s',
        '--source-instance-name',
        type=str,
        required=True,
        dest='source_instance_name',
        help='source instance name. this command use snapshot of source instance.'
    )
    parser.add_argument(
        '-t',
        '--target-instance-name',
        type=str,
        required=True,
        dest='target_instance_name',
        help='target recreate instance name.'
    )

    parser.add_argument(
        '--only-create',
        action='store_true',
        default=False,
        dest='is_only_create',
        help='not recreate, but create.'
    )

    parser.add_argument(
        '-c',
        '--instance-class',
        type=str,
        default='db.t2.micro',
        dest='instance_class',
        help='ex). db.t2.micro(default), db.t2.small,db.t2.medium,db.t2.large...'
    )

    args = parser.parse_args()
    return args.source_instance_name, args.target_instance_name, args.instance_class, args.is_only_create


def recreate_instance(source_instance_name, target_instance_name, instance_class):
    """
    source_instance_nameの最新のスナップショットをもとにtarget_instance_nameで
    指定されたインスタンスを再作成する
    :param str source_instance_name: 作成するインスタンスのものになるDB名
    :param str target_instance_name: 再作成するDB名
    :param str instance_class: RDSのインスタンスクラス
    :return:
    """

    default_logger.info('start RDS Re Maker.')
    # 新規作成時はサフィックスをつけておく
    tmp_new_instance_name = '{base_name}-{time_suffix}'.format(
        base_name=target_instance_name,
        time_suffix=datetime.datetime.now().strftime('%m%d%H%M')
    )
    # 既存DBリネーム時はtmpサフィックスをつけておく
    tmp_renamed_instance_name = '{base_name}-tmp'.format(base_name=target_instance_name)
    rds_re_maker = RdsMaker(
        region_name=REGION_NAME,
        az_name=AZ_NAME,
        aws_access_key=AWS_ACCESS_KEY,
        aws_rds_secret_key=AWS_RDS_SECRET_KEY,
        logger=default_logger
    )

    if not rds_re_maker.is_db_exist(target_instance_name):
        default_logger.critical('{} is not exist.'.format(target_instance_name))
        sys.exit(1)

    snapshot_identifier = rds_re_maker.get_latest_snapshot(source_instance_name)
    # 仮の名前でDB作成
    rds_re_maker.create_db_instance_sync(
        db_identifier=tmp_new_instance_name,
        snapshot_identifier=snapshot_identifier,
        instance_class=instance_class,
    )
    # 作成時には設定できない部分を変更
    rds_re_maker.change_db_instance_attributes_sync(db_identifier=tmp_new_instance_name, attributes={
        'DBParameterGroupName': DB_PARAMETER_GROUP,
        'BackupRetentionPeriod': 7,
        'VpcSecurityGroupIds': [VPC_SECURITY_GROUP_ID],
    })

    # 既存のインスタンスをリネーム
    rds_re_maker.rename_db_instance_sync(from_identifier=target_instance_name, to_identifier=tmp_renamed_instance_name)

    # 作成した新規インスタンスをリネームして同名にする
    rds_re_maker.rename_db_instance_sync(from_identifier=tmp_new_instance_name, to_identifier=target_instance_name)

    # もともとのインスタンス削除
    snapshot_name = rds_re_maker.delete_db_instance(db_identifier=tmp_renamed_instance_name)

    default_logger.info('end RDS Re Maker.')


def create_instance(source_instance_name, target_instance_name, instance_class):
    """
    source_instance_nameの最新のスナップショットをもとにtarget_instance_nameで
    指定されたインスタンスを作成する
    :param str source_instance_name: 作成するインスタンスのものになるDB名
    :param str target_instance_name: 再作成するDB名
    :param str instance_class: RDSのインスタンスクラス
    :return:
    """

    default_logger.info('start RDS Re Maker[only create mode].')

    rds_re_maker = RdsMaker(
        region_name=REGION_NAME,
        az_name=AZ_NAME,
        aws_access_key=AWS_ACCESS_KEY,
        aws_rds_secret_key=AWS_RDS_SECRET_KEY,
        logger=default_logger
    )

    # 再作成ではないので同名DBがある場合は終了する
    if rds_re_maker.is_db_exist(target_instance_name):
        default_logger.critical('{} is exist.'.format(target_instance_name))
        sys.exit(1)

    snapshot_identifier = rds_re_maker.get_latest_snapshot(source_instance_name)
    # DB作成
    rds_re_maker.create_db_instance_sync(
        db_identifier=target_instance_name,
        snapshot_identifier=snapshot_identifier,
        instance_class=instance_class,
    )
    # 作成時には設定できない部分を変更
    rds_re_maker.change_db_instance_attributes_sync(db_identifier=target_instance_name, attributes={
        'DBParameterGroupName': DB_PARAMETER_GROUP,
        'BackupRetentionPeriod': 7,
        'VpcSecurityGroupIds': [VPC_SECURITY_GROUP_ID],
    })

    default_logger.info('end RDS Re Maker[only create mode].')


if __name__ == '__main__':
    source_name, target_name, target_instance_class, is_only_create = init()
    if is_only_create:
        create_instance(source_name, target_name, target_instance_class)
    else:
        recreate_instance(source_name, target_name, target_instance_class)
