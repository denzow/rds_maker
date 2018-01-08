# coding:utf-8
import datetime
import time

from logging import getLogger, Formatter, StreamHandler, DEBUG

import boto3
import botocore.exceptions
# logger
default_logger = getLogger(__name__)
formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler = StreamHandler()
handler.setLevel(DEBUG)
handler.setFormatter(formatter)
default_logger.setLevel(DEBUG)
default_logger.addHandler(handler)


class RdsMakerException(Exception):
    """
    RDS作成中の例外
    """


class RdsMaker:
    """
    RDSを作成する
    """

    def __init__(self, region_name, az_name, aws_access_key, aws_rds_secret_key, logger=None):
        """
        :param str region_name: リージョン名
        :param str az_name: AZ名
        :param str aws_access_key: RDSFullControlを持つAWSアクセスキー
        :param str aws_rds_secret_key: RDSFullControlを持つAWSシークレットアクセスキー
        :param logger:
        """
        self.logger = logger or default_logger
        self.region_name = region_name
        self.az_name = az_name

        if not aws_access_key or not aws_rds_secret_key:
            raise RdsMakerException('AWS ACCESS KEY is not valid')

        self.logger.info('start RDS Maker.')
        self.rds = boto3.client(
            'rds',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_rds_secret_key,
            region_name=self.region_name
        )
        self.logger.info('connected via boto3.')

    def is_db_exist(self, db_identifier):
        """
        指定したDBが存在するか。ステータス取得が成功すればよしとする
        :param str db_identifier:
        :return: 存在するか
        :rtype: bool
        """
        try:
            _ = self._get_instance_status(db_identifier)
            return True
        except botocore.exceptions.ClientError:
            return False

    def get_latest_snapshot(self, db_identifier):
        """
        指定したインスタンスの最新のスナップショットを取得する
        :param str db_identifier: DBインスタンス名
        :return: スナップショット識別情報
        :rtype: str
        """
        row_snaps = self.rds.describe_db_snapshots(DBInstanceIdentifier=db_identifier)
        snapshots = row_snaps['DBSnapshots']
        if not snapshots:
            raise RdsMakerException('Not Found Valid Snapshot for {}'.format(db_identifier))

        # 最新のスナップショットを取得
        snapshot_identifier = snapshots[-1]['DBSnapshotIdentifier']
        self.logger.info('get latest snapshot of [{}] is [{}]'.format(db_identifier, snapshot_identifier))
        return snapshot_identifier

    def _get_instance_status(self, db_identifier):
        """
        指定したインスタンスのステータスを取得する
        :param str db_identifier: 確認するDBインスタンス名
        :return: 現在のステータス
        :rtype: str
        """
        return self.rds.describe_db_instances(DBInstanceIdentifier=db_identifier)['DBInstances'][0]['DBInstanceStatus']

    def _wait_available(self, db_identifier):
        """
        指定したインスタンスがavailableになるまで待機する。ただし変更操作の直後に
        実行するとそのままavailableであるため、一旦available以外になることを確認してから
        待機を行う
        :param str db_identifier: 確認するDBインスタンス名
        :rtype: None
        """

        once_not_available = False
        while True:
            status = self._get_instance_status(db_identifier)
            if once_not_available and status == 'available':
                break
            if not once_not_available and status != 'available':
                once_not_available = True
            self.logger.debug('wait available. now {}'.format(status))
            time.sleep(20)

    def _wait_status(self, db_identifier, request_status, limit_seconds=30 * 60):
        """
        期待したステータスになるまで待機する
        :param str db_identifier: 確認するDB名
        :param str request_status: 期待するステータス(available等)
        :param int limit_seconds: 待機する限界秒数
        :return: None
        """

        start_time = datetime.datetime.now()
        while True:
            status = self._get_instance_status(db_identifier)
            if status == request_status:
                break
            self.logger.debug('wait {} {}. now {}'.format(db_identifier, request_status, status))
            if (datetime.datetime.now() - start_time).seconds > limit_seconds:
                raise RdsMakerException('wait status operation timeout[over {}]'.format(limit_seconds))

            time.sleep(20)

    def create_db_instance_sync(self, db_identifier, snapshot_identifier, instance_class):
        """
        指定したスナップショットからDBインスタンスを作成する。
        作成したインスタンスがavailableになるまで待機する
        :param str db_identifier: 作成するDBインスタンス名
        :param str snapshot_identifier: 作成元になるスナップショット名
        :param str instance_class: 作成時のインスタンスクラス
        :return: 作成されたDBインスタンス名
        :rtype: str
        """
        self.logger.info('create instance [{}]'.format(db_identifier))
        _ = self.rds.restore_db_instance_from_db_snapshot(
            DBInstanceIdentifier=db_identifier,
            DBSnapshotIdentifier=snapshot_identifier,
            DBInstanceClass=instance_class,
            AvailabilityZone=self.az_name,
            PubliclyAccessible=False,
        )
        # 作成完了まで待機
        self._wait_available(db_identifier)
        self.logger.info('created instance')
        return db_identifier

    def change_db_instance_attributes_sync(self, db_identifier, attributes=None):
        """
        DBインスタンス作成時には指定できない属性を変更する
        :param str db_identifier: 変更対象のDBインスタンス名
        :param dict attributes: 変更する属性のDict(boto3の引数ベース)
        :return: DBインスタンス名
        :rtype: str
        """
        self.logger.info('modify instance [{}]'.format(db_identifier))
        if not attributes:
            return db_identifier

        attributes['DBInstanceIdentifier'] = db_identifier
        attributes['ApplyImmediately'] = True
        attributes['DBInstanceIdentifier'] = db_identifier

        self.rds.modify_db_instance(**attributes)
        self._wait_available(db_identifier)
        self.logger.info('modified instance')
        return db_identifier

    def rename_db_instance_sync(self, from_identifier, to_identifier, limit_seconds=30 * 60):
        """
        DBインスタンス名を変更する。変更完了まで待機する
        :param str from_identifier: 変更対象のDBインスタンス名
        :param str to_identifier: 変更先のDBインスタンス名
        :param int limit_seconds: 待機限界秒数(デフォルト30分(1800秒))
        :return: リネーム後のインスタンス名
        :rtype: str
        """
        self.logger.info('rename instance [{} -> {}]'.format(from_identifier, to_identifier))
        self.rds.modify_db_instance(
            DBInstanceIdentifier=from_identifier,
            NewDBInstanceIdentifier=to_identifier,
            ApplyImmediately=True
        )
        start_time = datetime.datetime.now()
        while True:
            status = None
            try:
                # リネームがある程度進むまではリネーム後のDB名ではNotFoundになる
                status = self._get_instance_status(to_identifier)
            except botocore.exceptions.ClientError as e:
                # 時間切れ
                if (datetime.datetime.now() - start_time).seconds > limit_seconds:
                    raise RdsMakerException('Rename operation timeout[over {}]'.format(limit_seconds))
                continue
            if status == 'available':
                break

        self.logger.info('renamed instance')
        return to_identifier

    def delete_db_instance(self, db_identifier):
        """
        指定したDBインスタンスを削除する。削除時にスナップショットを取得する
        :param str db_identifier: 削除対象DBインスタンス
        :return: 最終スナップショット名
        :rtype: str
        """
        self.logger.info('delete instance [{}]'.format(db_identifier))
        self._wait_status(db_identifier, 'available')
        snapshot_name = 'lsnap-{base_name}-{time_suffix}'.format(
            base_name=db_identifier,
            time_suffix=datetime.datetime.now().strftime('%m%d%H%M')
        )
        self.rds.delete_db_instance(
            DBInstanceIdentifier=db_identifier,
            SkipFinalSnapshot=False,
            FinalDBSnapshotIdentifier=snapshot_name,
        )
        self.logger.info('deleted instance')
        return snapshot_name
