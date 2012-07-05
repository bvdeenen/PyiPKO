import logging
import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class Operation(object):
    def __init__(self):
        self.exec_date = None
        self.order_date = None
        self.operation_type = None
        self.title = ''
        self.from_number = None
        self.from_addr = None
        self.amount = {'curr': None, 'val': None}
        self.ending_balance = {'curr': None, 'val': None}


class AccountHistory(object):
    def __init__(self):
        self.account = None
        self.date = {'since': None, 'to': None}
        self.filtering = None
        self.operations = list()


class Converter(object):
    def parse_from_XML(self, filename):
        import xml.etree.ElementTree as etree
        logger.info('Parsing from %s ...', filename)
        tree = etree.parse(filename)
        root = tree.getroot()
        #fetching account data
        self.account_history = AccountHistory()
        search = root.findall('search')[0]
        elem = search.findall('account')[0]
        self.account_history.account = elem.text
        elem = search.findall('date')[0]
        self.account_history.date = elem.attrib
        elem = search.findall('filtering')[0]
        self.account_history.filtering = elem.text
        #fetching operations list
        operations = root.findall('operations')[0]
        for operation in operations.findall('operation'):
            try:
                obj = Operation()
                elem = operation.findall('exec-date')[0]
                obj.exec_date = datetime.datetime.strptime(\
                        elem.text, '%Y-%m-%d')
                elem = operation.findall('order-date')[0]
                obj.order_date = datetime.datetime.strptime(\
                        elem.text, '%Y-%m-%d')
                elem = operation.findall('type')[0]
                obj.operation_type = elem.text
                elem = operation.findall('description')[0]
                if elem.text:
                    obj.title = str()
                    obj.from_addr = str()
                    obj.from_number = str()
                    for line in elem.text.splitlines():
                        if line.startswith('Tytu'):
                            obj.title = line.split(': ', 1)[1]
                        elif line.startswith('Dane adr. rach.'):
                            obj.from_addr = line.split(': ', 1)[1]
                        elif line.startswith('Nr rach.'):
                            obj.from_number = line.split(': ', 1)[1]
                        else:
                            obj.title = line
                elem = operation.findall('amount')[0]
                obj.amount['curr'] = elem.attrib['curr']
                obj.amount['val'] = elem.text
                elem = operation.findall('ending-balance')[0]
                obj.ending_balance['curr'] = elem.attrib['curr']
                obj.ending_balance['val'] = elem.text
                #add Operation to operations list
                self.account_history.operations.append(obj)
            except ValueError:
                logger.exception('Problem parsing operation data.')

    def parse_from_CSV(self, filename, encoding=None):
        import csv
        logger.info('Parsing from %s ...', filename)
        reader = csv.reader(open(filename, 'r', encoding=encoding),
                delimiter=',', quotechar='"')
        self.account_history = AccountHistory()
        for line, row in enumerate(reader):
            print(row)
            if line == 0:
                continue
            try:
                operation = Operation()
                operation.exec_date = datetime.datetime.strptime(
                        row[0], '%Y-%m-%d')
                operation.order_date = datetime.datetime.strptime(
                        row[1], '%Y-%m-%d')
                operation.operation_type = row[2]
                operation.amount['curr'] = row[4]
                operation.amount['val'] = row[3]
                operation.ending_balance['curr'] = row[4]
                operation.ending_balance['val'] = row[5]
                operation.description = row[6]
                try:
                    if row[7] in ('Nr rach.', 'Nr rach. przeciwst.'):
                        operation.from_number = line.split(': ', 1)[1]
                    if row[8] in ('Dane adr. rach.', 'Dane adr. rach. przeciwst.'):
                        operation.from_addr = line.split(': ', 1)[1]
                except IndexError:
                    operation.from_number = str()
                    operation.from_addr = str()
                #append to the operations list
                self.account_history.operations.append(operation)
                if line == 1:
                    self.account_history.date['since'] = row[0]
                self.account_history.date['to'] = row[1]
            except ValueError:
                logger.exception('Problem parsing operation data.')

    def to_mt940(self):
        # Header
        mt940 = str()
        mt940 += '\r\n'
        mt940 += ':20:{0}\r\n'.format('MT940')
        # Only polish accounts
        mt940 += ':25:/{0}{1}\r\n'.format('PL', self.account_history.account)
        mt940 += ':28C:{0:05}\r\n'.format(0)
        # Sum the balance from begining
        value_tmp = abs(Decimal(
                self.account_history.operations[-1].amount['val']))
        value_tmp += abs(Decimal(
                self.account_history.operations[-1].ending_balance['val']))
        # Format balance with comma, >0 value
        value = '{0:.2f}'.format(value_tmp,).replace('.', ',')
        ending_date = datetime.datetime.strptime(
                self.account_history.date['since'], '%Y-%m-%d')
        currency = self.account_history.operations[-1].ending_balance['curr']
        mt940 += ':60F:{0}{1}{2}{3}\r\n'.format(
                        'D' if value[0] == '-' else 'C',
                        ending_date.strftime('%y%m%d'),
                        currency.upper() if currency else '',
                        value if value else '')
        # Header end
        for operation in self.account_history.operations:
            operation_str = str(operation.amount['val'])
            # Operation description
            mt940 += ':61:{0}{1}{2}{3}{4}{5}{6:010}\r\n'.format(
                        operation.order_date.strftime('%y%m%d'),
                        operation.exec_date.strftime('%m%d'),
                        'D' if operation_str[0] == '-' else 'C',
                        '{0:.2f}'.format(abs(Decimal(operation.amount['val']))).replace('.', ','),
                        'S',
                        '034',
                        0)
            # Only one type of operation
            mt940 += ':86:{0}\r\n'.format('034',)
            mt940 += ':86:{0}{1}\r\n'.format('034~00', '')
            logger.debug('operation = %s', operation)
            logger.debug('operation.title = %s', operation.title)
            #Magic with description <=27 characters
            for line_num in range(6):
                title_format = '~2{0}{1}\r\n'
                start = line_num * 27
                line_len = 27
                title_line = operation.title[start: start + line_len]
                title_line = str(title_line) if title_line else chr(255)
                mt940 += title_format.format(line_num, title_line)
            mt940 += '~30{0}\r\n'.format(
                        operation.from_number[3:12].replace(' ', ''),)
            mt940 += '~31{0}\r\n'.format(
                        operation.from_number[13:].replace(' ', ''),)
            addr = operation.from_addr or ''
            mt940 += '~32{0}\r\n'.format(addr[0:27])
            mt940 += '~33{0}\r\n'.format(addr[27:27 + 27] or chr(255))
            mt940 += '~34{0}\r\n'.format('034')
            mt940 += '~38{0}{1}\r\n'.format('PL' if operation.from_number else '',
                        operation.from_number.replace(' ', ''))
            # If empty -> (char)255
            mt940 += '~63{0}\r\n'.format(chr(255))
            # Balance here?
            mt940 += '~64{0}\r\n'.format('')

        # Footer
        footer_date = datetime.datetime.strptime(
                self.account_history.date['to'], '%Y-%m-%d')

        currency = self.account_history.operations[0].ending_balance['curr']
        value = self.account_history.operations[0].ending_balance['val']
        mt940 += ':62F:{0}{1}{2}{3}\r\n'.format(
                    'D' if value[0] == '-' else 'C',
                    footer_date.strftime('%y%m%d'),
                    currency.upper() if currency else '',
                    value.replace('.', ',', 1)[1:] if value else '')
        mt940 += ':64:{0}{1}{2}{3}\r\n'.format(
                    'D' if value[0] == '-' else 'C',
                    footer_date.strftime('%y%m%d'),
                    currency.upper() if currency else '',
                    value.replace('.', ',', 1)[1:] if value else '')
        mt940 += ':86:NAME ACCOUNT OWNER:\r\n'
        mt940 += ':86:ACCOUNT DESCRIPTION:\r\n'
        mt940 += '-\r\n'
        return mt940
