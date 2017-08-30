import boto3
import json
import os
import pymysql
import requests
import sys

def es_automate(file):
    file = os.path.abspath(os.path.expanduser(file))
    try:
        with open(file) as data_file:
            data = json.load(data_file)
    except Exception as e:
        print('Error. Unable to load the setting file.')
        sys.exit()

    # start to handle Elastic Search here
    client = boto3.client('es',
                          region_name=data.get('region', ''),
                          aws_access_key_id=data.get('accessKey', ''),
                          aws_secret_access_key=data.get('secretKey', ''))

    for item in data.get('elasticSearch'):
        if not item.get('skip'):
            config = {}
            if item.get('dedicatedMasterEnabled'):
                config = {'InstanceType': item.get('config').get('instanceType'),
                          'InstanceCount': item.get('config').get('instanceCount'),
                          'DedicatedMasterEnabled': True,
                          'ZoneAwarenessEnabled': item.get('config').get('zoneAwarenessEnabled'),
                          'DedicatedMasterType': item.get('config').get('dedicatedMasterType'),
                          'DedicatedMasterCount': item.get('config').get('dedicatedMasterCount')}
            else:
                config = {'InstanceType': item.get('config').get('instanceType'),
                          'InstanceCount': item.get('config').get('instanceCount'),
                          'DedicatedMasterEnabled': False,
                          'ZoneAwarenessEnabled': item.get('config').get('zoneAwarenessEnabled')}

            response = client.create_elasticsearch_domain(
                        DomainName=item.get('domainName'),
                        ElasticsearchVersion=item.get('version'),
                        ElasticsearchClusterConfig=config,
                        EBSOptions={
                            'EBSEnabled': item.get('ebsOptions').get('enabled'),
                            'VolumeType': item.get('ebsOptions').get('volumeType'),
                            'VolumeSize': item.get('ebsOptions').get('volumeSize')
                        },
                        AccessPolicies=item.get('accessPolicies'),
                        SnapshotOptions={
                            'AutomatedSnapshotStartHour': item.get('automatedSnapshotStartHour')
                        })
            
            print(response)

            #create indices
            connection = pymysql.connect(host=item.get('dbServer'),
                                         user=item.get('dbUser'),
                                         password=item.get('dbPassword'),
                                         db=item.get('db'),
                                         charset='utf8mb4',
                                         cursorclass=pymysql.cursors.DictCursor)

            with connection.cursor() as cursor:
                sql = "SELECT * from {}".format(item.get('view'))
                cursor.execute(sql)
                cursor.fetchall()

if __name__ == '__main__':
    es_automate('~/Documents/config/package.json')