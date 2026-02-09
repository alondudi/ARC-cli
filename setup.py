from setuptools import setup, find_packages

setup(
    name='arc-cli',
    version='1.0.0',
    author='Alon',
    description='ARC - Amazon Resources Controller CLI',

    long_description=open('README.md', encoding='utf-8').read() if hasattr(open('README.md'), 'read') else '',
    long_description_content_type='text/markdown',

    packages=find_packages(),

    py_modules=['arc_cli'],

    install_requires=[
        'Click>=8.0',
        'boto3>=1.26.0',
        'colorama',
        'rich',
    ],

    entry_points='''
        [console_scripts]
        arc=arc_cli:arc
    ''',

    python_requires='>=3.7',
)