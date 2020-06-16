# pollscore

A python package for scoring poll response reports such as generated by Zoom
and processing them into a format suitable for upload in a course management system
such as Canvas.

## Installation

This is a python program that requires the ``pandas`` package. The standard python installation tools should be able to take care of the dependencies. If `pip` refers to the Python 3 version, then you should be able to install the package using

    pip install git+https://github.com/nbruin/pollscore --user

or, alternatively, you might need

    pip3 install git+https://github.com/nbruin/pollscore --user

or some other way of performing "pip installs" on your system.

## Usage

Pollscore expects its data in a directory (usually the current director). It consists of

 * `config` - a configuration file.
 * `roster.csv` - a class roster used to format the submission file for upload into the course management system. The actual name and location of this file is specified in `config`.
 * `PollReport-*.csv` - Poll response reports from, for instance, Zoom. The actual names and locations of these files are specified in `config`. Wildcards are allowed, so new reports can be taken into account simply by saving the file in the appropriate directory.

See the included `example` directory for an example of a layout that works. In absence of further documentation, the `config` file there documents features by example.

The installation of pollscore includes a command-line script. If the `example` directory contains the information required, then

    $ cd example
    $ pollscore

should produce some output in the terminal and a submission file ready for upload. If the script does not work, then

    $ python3 -m pollscore.pollscore

might.

For more elaborate data analysis, pollscore can also be used interactively. A `jupyter` notebook is probably the most convenient environment to use it. Most data is represented using pandas dataframes, and all the usual pandas data analysis tools can be used on them. To get started, the following are probably useful:

```python
>>> from pollscore.pollscore import Poll
>>> P = Poll("config")
>>> P.response_table() #a table of all responses
>>> P.match() #a dictionary displaying the matching with the course roster
>>> P.participation_table() #scores by participation
>>> P.correctness_table() #scores by correctness
>>> P.totals_table() #total scores (the above two summed)
>>> P.matched_roster() #roster of matched students
>>> P.roster_table() #table ready for upload
>>> P.write_submission() #routine that writes the submission csv file
```
