from setuptools import setup, find_packages

setup(
    name='arc-cli',
    version='0.1.1',
    author='Alon',
    description='ARC - Amazon Resources Controller CLI',
    long_description=open('README.md').read() if hasattr(open('README.md'), 'read') else '',
    long_description_content_type='text/markdown',

    py_modules=['arc_cli', 'aws_manager'],

    install_requires=[
        'Click>=8.0',
        'boto3>=1.26.0',
        'colorama',
        'rich',
    ],

    entry_points={
        'console_scripts': [
            'arc = arc_cli:arc',
        ],
    },

    python_requires='>=3.7',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)