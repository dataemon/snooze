#!/usr/bin/python36

from bson.json_util import dumps
from subprocess import run, CalledProcessError, PIPE
from jinja2 import Template

from snooze.plugins.action import Action

from logging import getLogger
log = getLogger('snooze.action.script')

class Script(Action):
    def __init__(self, core):
        super().__init__(core)

    def pprint(self, content):
        output = content.get('script')
        arguments = content.get('arguments')
        if arguments:
            output += ' ' + ' '.join(map(lambda x: x[0]+' '+x[1], arguments))
        return output

    def send(self, record, content):
        script = [content.get('script', '')]
        arguments = content.get('arguments', [])
        json = content.get('json', False)
        for argument in arguments:
            if type(argument) is str:
                script += interpret_jinja([argument], record)
            if type(argument) is list:
                script += interpret_jinja(argument, record)
            if type(argument) is dict:
                script += sum([interpret_jinja([k, v], record) for k, v in argument])
        try:
            log.debug("Will execute notification script `{}`".format(' '.join(script)))
            stdin = dumps(record) if json else None
            process = run(script, stdout=PIPE, input=stdin, encoding='ascii')
            log.debug('stdout: ' + str(process.stdout))
            log.debug('stderr: ' + str(process.stderr))
            self.core.stats.inc('snooze_notification_sent', {'type': self.name, 'name': content.get('name', '')})
        except CalledProcessError as e:
            self.core.stats.inc('snooze_notification_error', {'type': self.name, 'name': content.get('name', '')})
            log.error("Notification {} could not run `{}`. STDIN = {}, {}".format(
                name, ' '.join(script), stdin, e.output)
            )

def interpret_jinja(fields, record):
    return list(map(lambda field: Template(field).render(record), fields))
