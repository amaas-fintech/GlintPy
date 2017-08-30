from amaasinfra.data.data_setup import DatabaseSetter
import boto3
import json
import os
import pymysql
import sys
from random import choice
from string import ascii_lowercase
from time import sleep

def stack_automate(file):
    # # setting up aws account
    # if len(sys.argv) < 2 or (sys.argv[1] != '-f' and sys.argv[1] != '--file'):
    #     raise ValueError('Missing settings file path argument. Supply a settings file path with -f argument.')
    # input_file = sys.argv[2]
    file = os.path.abspath(os.path.expanduser(file))
    try:
        with open(file) as data_file:
            data = json.load(data_file)
    except Exception as e:
        print('Error. Unable to load the setting file.')
        sys.exit()

    print('Initializing AWS Stack services...')

    # Creating new VPCs
    ec2_res = boto3.resource('ec2',
                             region_name=data.get('region', ''),
                             aws_access_key_id=data.get('accessKey', ''),
                             aws_secret_access_key=data.get('secretKey', ''))

    ec2_cli = ec2_res.meta.client

    elastic_ip = {}
    if data.get('elasticIP'):
        print('Creating Elastic IP...')
        elastic_ip = ec2_cli.allocate_address(Domain='vpc')

    for item in data.get('vpcs'):
        if not item.get('skip'):
            print('Creating VPC {}...'.format(item.get('cidrBlock')))
            response = {}
            if item.get('defaultVpc'):
                response = ec2_cli.create_default_vpc()
            else:
                response = ec2_cli.create_vpc(
                    CidrBlock=item.get('cidrBlock'),
                    AmazonProvidedIpv6CidrBlock=False,
                    InstanceTenancy=item.get('instanceTenancy'))

            new_vpc_id = response.get('Vpc').get('VpcId')
            print('Creating new subnets...')
            created_subnets = [item.get('CidrBlock') for item in ec2_cli.describe_subnets().get('Subnets')]
            new_subnets = [item.get('cidr') for item in item.get('subnets')]

            to_be_created_subnets = list(set(new_subnets) - set(created_subnets))
            for cidr in to_be_created_subnets:
                print('Creating subnet {}...'.format(cidr))
                for subnet_item in item.get('subnets'):
                    if cidr == subnet_item.get('cidr'):
                        subnet = ec2_cli.create_subnet(
                            AvailabilityZone=subnet_item.get('availabilityZone'),
                            CidrBlock=cidr,
                            VpcId=new_vpc_id)

            if data.get('elasticIP'):
                # once additional subnets been created, describe all subnets again and create NAT gateways
                created_subnets = [item for item in ec2_cli.describe_subnets().get('Subnets')]

                nats = [item for item in item.get('subnets') if item.get('nat')]

                for nat in nats:
                    for subnet in created_subnets:
                        if nat.get('cidr') == subnet.get('CidrBlock'):
                            print('Creating NAT Gateway for subnet {}...'.format(subnet.get('SubnetId')))
                            ec2_cli.create_nat_gateway(AllocationId=elastic_ip.get('AllocationId'),
                                                       SubnetId=subnet.get('SubnetId'))

            #creating security groups other than default group
            for sg in item.get('securityGroups'):
                response = ec2_cli.create_security_group(Description=sg.get('description'),
                                                            GroupName=sg.get('name'),
                                                            VpcId=new_vpc_id)
                grp_id = response['GroupId']
                ec2_cli.authorize_security_group_ingress(GroupId=grp_id,
                                                        GroupName=sg.get('name'),
                                                        IpPermissions=sg.get('ingressRules'))

    #Createing IAM roles and custom policies    
    client = boto3.client('iam',
                          region_name=data.get('region', ''),
                          aws_access_key_id=data.get('accessKey', ''),
                          aws_secret_access_key=data.get('secretKey', ''))
    for item in data.get('customPolicies'):
        print('Creating new policy {}...'.format(item.get('name')))
        try:
            client.create_policy(PolicyName=item.get('name'),
                                 Path=item.get('path', '/'),
                                 PolicyDocument=item.get('document'),
                                 Description=item.get('description', ''))
        except Exception as e:
            print(e)
            continue

    
    for item in data.get('iamRoles'):
        print('Creating new IAM role {}...'.format(item.get('roleName')))
        try:
            client.create_role(Path=item.get('path', '/'),
                                RoleName=item.get('roleName'),
                                AssumeRolePolicyDocument=item.get('assumedRole'),
                                Description=item.get('description', ''))

            for policy in item.get('policies'):
                print('Attaching policy {} to IAM role {}...'.format(policy,
                                                                     item.get('roleName')))
                client.attach_role_policy(RoleName=item.get('roleName'),
                                          PolicyArn=policy)
                client.put_role_policy(RoleName=item.get('roleName'),
                                       PolicyName=item.get('roleName')+ (''.join(choice(ascii_lowercase) for i in range(12))),
                                       PolicyDocument=item.get('inlinePolicy'))
        except Exception as e:
            print(e)
            continue

    # Creating new RDS
    client = boto3.client('rds',
                          region_name=data.get('region', ''),
                          aws_access_key_id=data.get('accessKey', ''),
                          aws_secret_access_key=data.get('secretKey', ''))

    for item in data.get('rds'):
        if not item.get('skip'):
            print('Creating RDS subnet group...')  
            subnet_ids = [sub_item.get('SubnetId') for sub_item in ec2_cli.describe_subnets(Filters=[{'Name': 'cidrBlock', 'Values': item.get('subnetGroupSubnets')}]).get('Subnets')]

            security_grp_ids = [sub_item.get('GroupId') for sub_item in ec2_cli.describe_security_groups(Filters=[{'Name': 'group-name', 'Values': item.get('securityGroups')}]).get('SecurityGroups')]
            client.create_db_subnet_group(
                DBSubnetGroupName=item.get('subnetGroup'),
                DBSubnetGroupDescription='{} Subnet Group'.format(item.get('subnetGroup')),
                SubnetIds=subnet_ids
            )
            response = client.create_db_instance(DBInstanceIdentifier=item.get('identifier'),
                                                 AllocatedStorage=item.get('allocatedStorage'),
                                                 DBInstanceClass=item.get('instanceClass'),
                                                 Engine=item.get('engine'),
                                                 EngineVersion=item.get('engineVersion'),
                                                 LicenseModel=item.get('licenseModel'),
                                                 MasterUsername=item.get('username'),
                                                 MasterUserPassword=item.get('password'),
                                                 VpcSecurityGroupIds=security_grp_ids,
                                                 StorageEncrypted=item.get('storageEncrypted'),
                                                 #AvailabilityZone=item.get('availabilityZone'),
                                                 DBSubnetGroupName=item.get('subnetGroup'),
                                                 PreferredBackupWindow=item.get('backupWindow'),
                                                 BackupRetentionPeriod=item.get('backupRetentionPeriod'),
                                                 Port=item.get('port'),
                                                 MultiAZ=item.get('multipleAZ'),
                                                 AutoMinorVersionUpgrade=item.get('autoMinorVersionUpgrade'),
                                                 PubliclyAccessible=item.get('publiclyAccessible'),
                                                 StorageType=item.get('storageType'))

            print('Waiting for endpoint to be ready, this may take a while...')
            new_db_endpoint = ''
            db_identifier = response.get('DBInstance').get('DBInstanceIdentifier')
            while True:
                sleep(5)
                print('Checking for new endpoint...')
                the_instance = client.describe_db_instances(DBInstanceIdentifier=db_identifier).get('DBInstances')[0]
                if the_instance.get('Endpoint', None):
                    new_db_endpoint = the_instance.get('Endpoint').get('Address')
                    break
            
            #check if replication required
            if item.get('requireReplication'):
                """This needs better implementation to handle both encrypted and non-encrypted source instances"""
                # print('Creating DB replication...')
                # print(client.create_db_instance_read_replica(DBInstanceIdentifier=item.get('identifier')+'-replica',
                #                                              SourceDBInstanceIdentifier=item.get('identifier'),
                #                                              DBInstanceClass=item.get('instanceClass'),
                #                                              AvailabilityZone=item.get('availabilityZone'),
                #                                              Port=item.get('port'),
                #                                              AutoMinorVersionUpgrade=item.get('autoMinorVersionUpgrade'),
                #                                              PubliclyAccessible=item.get('publiclyAccessible'),
                #                                              Tags=[{'Key': 'Name',
                #                                                     'Value': item.get('identifier')+'-replica'}],
                #                                              StorageType=item.get('storageType'),
                #                                              CopyTagsToSnapshot=True,                                                
                #                                              SourceRegion=data.get('region', '')))

            db_setter = DatabaseSetter()
            for db in item.get('databases'):
                db_config={'db_server': new_db_endpoint,
                           'db_username': item.get('username'),
                           'db_password': item.get('password'),
                           'ignore': ['.DS_Store'],
                           'table_path': db.get('tablePath') if os.path.isabs(db.get('tablePath')) \
                                         else os.path.abspath(os.path.expanduser(db.get('tablePath')))}
                if db.get('dataPath', None):
                    db_config.update({'data_path': db.get('dataPath') if os.path.isabs(db.get('dataPath')) \
                                      else os.path.abspath(os.path.expanduser(db.get('dataPath')))})
                db_setter.recreate(schema=db.get('name'), environment='automation', db_config=db_config)
                db_setter.recreate(schema='unittest_'+db.get('name'), environment='automation', 
                                   db_config=db_config)
        elif item.get('endpoint'):
            db_setter = DatabaseSetter()
            for db in item.get('databases'):
                db_config={'db_server': item.get('endpoint'),
                           'db_username': item.get('username'),
                           'db_password': item.get('password'),
                           'ignore': ['.DS_Store'],
                           'table_path': db.get('tablePath') if os.path.isabs(db.get('tablePath')) \
                                         else os.path.abspath(os.path.expanduser(db.get('tablePath')))}
                if db.get('dataPath', None):
                    db_config.update({'data_path': db.get('dataPath') if os.path.isabs(db.get('dataPath')) \
                                      else os.path.abspath(os.path.expanduser(db.get('dataPath')))})

                db_setter.recreate(schema=db.get('name'), environment='automation', 
                                   db_config=db_config)                
                db_setter.recreate(schema='unittest_'+db.get('name'), environment='automation', 
                                   db_config=db_config)
                
    #start to handle CloudWatch alarms here
    client = boto3.client('cloudwatch',
                          region_name=data.get('region', ''),
                          aws_access_key_id=data.get('accessKey', ''),
                          aws_secret_access_key=data.get('secretKey', ''))

    
    
    for item in data.get('cloudWatch').get('alarms'):
        if not item.get('skip'):
            print('Creating CloudWatch alarm {}...'.format(item.get('name')))
            dimensions = []
            for dim in item.get('dimensions'):
                dimensions.append({'Name': dim.get('name'), 'Value': dim.get('value')})

            client.put_metric_alarm(AlarmName=item.get('name'),
                                    AlarmDescription=item.get('description'),
                                    ActionsEnabled=item.get('enabled'),
                                    AlarmActions=["arn:aws:sns:{}:{}:{}".format(data.get('region'), data.get('awsClientID'), item.get('alarmAction')[0])],
                                    MetricName=item.get('metricName'),
                                    Namespace=item.get('namespace'),
                                    Statistic=item.get('statistic'),
                                    Dimensions=dimensions,
                                    Period=item.get('period'),
                                    Unit=item.get('unit'),
                                    EvaluationPeriods=item.get('evaluationPeriods'),
                                    Threshold=item.get('threshold'),
                                    ComparisonOperator=item.get('comparisonOperator'))
        
    #start to handle SNS here
    client = boto3.client('sns',
                          region_name=data.get('region', ''),
                          aws_access_key_id=data.get('accessKey', ''),
                          aws_secret_access_key=data.get('secretKey', ''))

    for item in data.get('sns'):
        if not item.get('skip'):
            print('Creating SNS topic {}...'.format(item.get('name')))
            client.create_topic(Name=item.get('name'))

    #start to handle DynamoDB here
    client = boto3.client('dynamodb',
                          region_name=data.get('region', ''),
                          aws_access_key_id=data.get('accessKey', ''),
                          aws_secret_access_key=data.get('secretKey', ''))

    for item in data.get('dynamoDBs'):
        if not item.get('skip'):
            print('Creating dynamoDB {}...'.format(item.get('name')))
            try:
                client.create_table(AttributeDefinitions=[{'AttributeName': attr.get('name'),
                                                        'AttributeType': attr.get('type')} for attr in item.get('attributeDefinitions')],
                                    TableName=item.get('name'),
                                    KeySchema=[{'AttributeName': attr.get('name'),
                                                'KeyType': attr.get('type')} for attr in item.get('keySchema')],
                                    ProvisionedThroughput={'ReadCapacityUnits': item.get('provisionedThroughput').get('readCapacityUnits'),
                                                        'WriteCapacityUnits': item.get('provisionedThroughput').get('writeCapacityUnits')})

            except Exception as e:
                print(e)
                continue

    # # start to handle SQS here    
    # client = boto3.client('sqs',
    #                       region_name=data.get('region', ''),
    #                       aws_access_key_id=data.get('accessKey', ''),
    #                       aws_secret_access_key=data.get('secretKey', ''))

    # for item in data.get('sqs'):