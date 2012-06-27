import logging
import datetime

logger = logging.getLogger(__name__)

class Operation(object):
    def __init__(self):
        self.exec_date = None
        self.order_date = None
        self.operation_type = None
        self.title = ''
        self.from_number = None
        self.from_addr = None
        self.amount = {'curr':None, 'val':None}
        self.ending_balance = {'curr':None, 'val':None}

class AccountHistory(object):
    def __init__(self):
        self.account = None
        self.date = {'since':None, 'to':None}
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
                    for line in elem.text.splitlines():
                        if line.startswith('Tytu'):
                            obj.title = line.split(': ', 1)[1]
                        elif line.startswith('Dane adr. rach.'):
                            obj.from_addr = line.split(': ', 1)[1]
                        elif line.startswith('Nr rach.'):
                            obj.from_number = line.split(': ', 1)[1]
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
        for row in reader:
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
                #append to the operations list
                self.account_history.operations.append(operation)
            except ValueError:
                logger.exception('Problem parsing operation data.')

    def to_mt940(self):
        mt940 = str()
        mt940 += ':20:{0}\n\r'.format('MT940')
        mt940 += ':25:{0}{1}\n\r'.format('PL', self.account_history.account)
        mt940 += ':28C:{0}\n\r'.format('')
        mt940 += ':60F:{0}{1}{2}{3}\n\r'.format('', '', '', '')
        mt940 += ':61:{0} {1}\n\r'.format('', '')
        for operation in self.account_history.operations:
            mt940 += ':86:{0}{1}\n\r'.format('020~00', '')
            logger.debug('operation = %s', operation)
            logger.debug('operation.title = %s', operation.title)
            for line_num in range(6):
                title_format = '~2{0}{1}\n\r'
                start = line_num * 27
                line_len = 27
                title_line = operation.title[start : start + line_len]
                title_line = str(title_line) if title_line else chr(255)
                mt940 += title_format.format(line_num, title_line)
            mt940 += '~30{0}\n\r'.format('')
            mt940 += '~31{0}\n\r'.format(operation.from_number)
            addr = operation.from_addr or ''
            mt940 += '~32{0}\n\r'.format(addr[0:27])
            mt940 += '~33{0}\n\r'.format(addr[27:27+27] or chr(255))
            mt940 += '~38{0}\n\r'.format('')
            mt940 += '~60{0}\n\r'.format('')
            mt940 += '~63{0}\n\r'.format('')
        ending_date = datetime.datetime.strptime(
                self.account_history.date['to'], '%Y-%m-%d')
        currency = self.account_history.operations[-1].ending_balance['curr']
        value = self.account_history.operations[-1].ending_balance['val']
        mt940 += ':62F:{0}{1}{2}{3}\n\r'.format('D' if value[0] == '-' else 'C',
                ending_date.strftime('%y%m%d'),
                currency.upper() if currency else '',
                value.replace('.', ',', 1)[1:] if value else '')
        mt940 += ':64:{0}{1}{2}{3}\n\r'.format('D' if value[0] == '-' else 'C',
                ending_date.strftime('%y%m%d'),
                currency.upper() if currency else '',
                value.replace('.', ',', 1)[1:] if value else '')
        mt940 += '-\n\r'
        return mt940
