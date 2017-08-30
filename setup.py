from setuptools import setup, find_packages

setup(
    name='glintpy',
    keywords=['argomi', 'automation', 'aws'],
    description='An AWS service automation tools for the missing pieces of CloudFormation',
    license='Apache License 2.0',
    install_requires=['boto3', 'pymysql', 'requests', 'amaasinfra'],
    version='0.0.9.7',
    entry_points={
          'console_scripts': [
              'glint = backendautomation.glint:master_command'
          ]
      },
    author='Argomi Pte Ltd',
    author_email='cheng.chen@argomi.com',
    packages=find_packages(),
    platforms='any',
)
