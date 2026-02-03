from setuptools import setup

setup(
    name='arc',
    version='0.1.0',
    py_modules=['arc_cli', 'aws_manager'],
    install_requires=[
        'Click',
        'boto3',
    ],
    entry_points={
        'console_scripts': [
            'arc = arc_cli:arc',
        ],
    },
)