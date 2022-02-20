import datetime
import hashlib
import json
import re
from lxml import etree
# from geopy import Nominatim
import pandas as pd
import numpy as np


from src.bstsouecepkg.extract import Extract
from src.bstsouecepkg.extract import GetPages


class Handler(Extract, GetPages):
    base_url = 'https://portal.ct.gov'
    NICK_NAME = base_url.split('//')[-1]
    fields = ['overview']
    overview = {}
    tree = None
    api = None

    header = {
        'User-Agent':
            'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
        # 'Accept':
        #     'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9;application/json',
        # 'accept-language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7',
        # 'Content-Type': 'text/html; charset=utf-8'
    }

    def getpages(self, searchquery):
        result = []
        url = f'https://portal.ct.gov/-/media/CID/1_Lists/Licencom.pdf'
        df = self.getpages_pdf(searchquery=searchquery, pages='all', file_base_url=url, search_column='1')
        desired_width = 620

        pd.set_option('display.width', desired_width)

        np.set_printoptions(linewidth=desired_width)

        pd.set_option('display.max_columns', 10)

        for page in df:
            #print(page)
            #addresses = page.iloc[:, 5].str.replace('\r', ' ')
            col1 = page.iloc[:, 0].astype(str).str.replace('\r', ' ')
            col2 = page.iloc[:, 1].astype(str).str.replace('\r', ' ')
            col3 = page.iloc[:, 2].astype(str).str.replace('\r', ' ')
            col4 = page.iloc[:, 3].astype(str).str.replace('\r', ' ')
            col5 = page.iloc[:, 4].astype(str).str.replace('\r', ' ')
            for c1, c2, c3, c4, c5 in zip(col1, col2, col3, col4, col5):
                if str(c1) != 'nan':
                    if searchquery.lower() in c1.lower():
                        result.append(f'{c1}=?{c2}=?{c3}=?{c4}=?{c5}')

         #
        # for url in urls:
        #     self.get_working_tree_api(url, 'tree')
        #     company_names = self.get_by_xpath(
        #         f'//div[@class="grid-container"]/ul/li[2]/text()[contains(translate(., "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{searchquery.lower()}")]')
        #     if company_names:
        #         for name in company_names:
        #             addr = self.get_by_xpath(
        #                 f'//div[@class="grid-container"]/ul/li[2]/text()[contains(., "{name}")]/../../li[3]/text()')
        #             buss = self.get_by_xpath('//p[@class="composite-title"]/text()')
        #             result.append(f'{name}?={addr[0]}?={buss[0]}')
        return result

    def get_by_xpath(self, xpath):
        try:
            el = self.tree.xpath(xpath)
        except Exception as e:
            print(e)
            return None
        if el:
            if type(el) == str or type(el) == list:
                el = [i.strip() for i in el]
                el = [i for i in el if i != '' and i != 'n/a']
            return el
        else:
            return None

    def reformat_date(self, date, format):
        date = datetime.datetime.strptime(date.strip(), format).strftime('%Y-%m-%d')
        return date

    def get_business_class(self, xpathCodes=None, xpathDesc=None, xpathLabels=None):
        res = []
        if xpathCodes:
            codes = self.get_by_xpath(xpathCodes)
        if xpathDesc:
            desc = self.get_by_xpath(xpathDesc)
        if xpathLabels:
            labels = self.get_by_xpath(xpathLabels)

        for c, d, l in zip(codes, desc, labels):
            temp = {
                'code': c.split(' (')[0],
                'description': d,
                'label': l.split('(')[-1].split(')')[0]
            }
            res.append(temp)
        if res:
            self.overview['bst:businessClassifier'] = res

    def get_post_addr(self, tree):
        addr = self.get_by_xpath(tree, '//span[@id="lblMailingAddress"]/..//text()', return_list=True)
        if addr:
            addr = [i for i in addr if
                    i != '' and i != 'Mailing Address:' and i != 'Inactive' and i != 'Registered Office outside NL:']
            if addr[0] == 'No address on file':
                return None
            if addr[0] == 'Same as Registered Office' or addr[0] == 'Same as Registered Office in NL':
                return 'Same'
            fullAddr = ', '.join(addr)
            temp = {
                'fullAddress': fullAddr if 'Canada' in fullAddr else (fullAddr + ' Canada'),
                'country': 'Canada',

            }
            replace = re.findall('[A-Z]{2},\sCanada,', temp['fullAddress'])
            if not replace:
                replace = re.findall('[A-Z]{2},\sCanada', temp['fullAddress'])
            if replace:
                torepl = replace[0].replace(',', '')
                temp['fullAddress'] = temp['fullAddress'].replace(replace[0], torepl)
            try:
                zip = re.findall('[A-Z]\d[A-Z]\s\d[A-Z]\d', fullAddr)
                if zip:
                    temp['zip'] = zip[0]
            except:
                pass
        # print(addr)
        # print(len(addr))
        if len(addr) == 4:
            temp['city'] = addr[-3]
            temp['streetAddress'] = addr[0]
        if len(addr) == 5:
            temp['city'] = addr[-4]
            temp['streetAddress'] = addr[0]
        if len(addr) == 6:
            temp['city'] = addr[-4]
            temp['streetAddress'] = ', '.join(addr[:2])

        return temp

    def get_address(self, xpath=None, zipPattern=None, key=None, returnAddress=False, addr=None):
        if xpath:
            addr = self.get_by_xpath(xpath)
        if key:
            addr = self.get_by_api(key)
        if addr:

            addr = addr[1]

            if '\n' in addr:
                splitted_addr = addr.split('\n')
            if ', ' in addr:
                splitted_addr = addr.split(', ')

            addr = addr.replace('\n', ' ')
            addr = addr[0] if type(addr) == list else addr
            temp = {
                'fullAddress': addr,
            }
            if zipPattern:
                zip = re.findall(zipPattern, addr)
                if zip:
                    temp['zip'] = zip[0]
            try:
                patterns = ['Suite\s\d+']
                for pattern in patterns:
                    pat = re.findall(pattern, addr)
                    if pat:
                        first_part = addr.split(pat[0])
                        temp['streetAddress'] = first_part[0] + pat[0]
            except:
                pass
            try:
                street = addr.split('Street')
                if len(street) == 2:
                    temp['streetAddress'] = street[0] + 'Street'

                # if temp['streetAddress']:
                #     temp['streetAddress'] = splitted_addr[0]
            except:
                pass
            try:
                # city = addr.replace(temp['zip'], '')
                # city = city.replace(temp['streetAddress'], '')
                # city = city.replace(',', '').strip()
                # city = re.findall('[A-Z][a-z]+', city)
                temp['city'] = addr.split(' ')[-1].replace('.', '')
                # temp['fullAddress'] += f", {temp['city']}"
            except:
                pass
            temp['fullAddress'] += ', Nigeria'
            temp['fullAddress'] = temp['fullAddress'].replace('.,', ',')
            if returnAddress:
                return temp
            self.overview['mdaas:RegisteredAddress'] = temp

    def getSpecialAddress(self):
        streetAddr = self.get_by_xpath(
            '//h6/text()[contains(., "Registered address")]/../following-sibling::div[1]//div[@class="row"]/div/text()[contains(., "Street address")]/../following-sibling::div[1]/text()')
        temp = {}
        if streetAddr:
            temp['streetAddress'] = streetAddr[0]
        city = self.get_by_xpath(
            '//h6/text()[contains(., "Registered address")]/../following-sibling::div[1]//div[@class="row"]/div/text()[contains(., "Locality")]/../following-sibling::div[1]/text()')
        if city:
            temp['city'] = city[0]

        zip = self.get_by_xpath(
            '//h6/text()[contains(., "Registered address")]/../following-sibling::div[1]//div[@class="row"]/div/text()[contains(., "Postal code")]/../following-sibling::div[1]/text()')
        if zip:
            temp['zip'] = zip[0]

        country = self.get_by_xpath(
            '//h6/text()[contains(., "Registered address")]/../following-sibling::div[1]//div[@class="row"]/div/text()[contains(., "Country")]/../following-sibling::div[1]/text()')
        if country:
            temp['country'] = country[0]

        if temp:
            temp['fullAddress'] = ', '.join(temp.values())
            self.overview['mdaas:RegisteredAddress'] = temp

    def get_prev_names(self, tree):
        prev = []
        names = self.get_by_xpath(tree,
                                  '//table[@id="tblPreviousCompanyNames"]//tr[@class="row"]//tr[@class="row"]//td[1]/text() | //table[@id="tblPreviousCompanyNames"]//tr[@class="row"]//tr[@class="rowalt"]//td[1]/text()',
                                  return_list=True)
        dates = self.get_by_xpath(tree,
                                  '//table[@id="tblPreviousCompanyNames"]//tr[@class="row"]//tr[@class="row"]//td[2]/span/text() | //table[@id="tblPreviousCompanyNames"]//tr[@class="row"]//tr[@class="rowalt"]//td[2]/span/text()',
                                  return_list=True)
        print(names)
        if names:
            names = [i for i in names if i != '']
        if names and dates:
            for name, date in zip(names, dates):
                temp = {
                    'name': name,
                    'valid_to': date
                }
                prev.append(temp)
        return prev

    def getFrombaseXpath(self, tree, baseXpath):
        pass

    def get_by_api(self, key):
        try:
            el = self.api[key]
            return el
        except:
            return None

    def fill_identifiers(self, xpathTradeRegistry=None, xpathOtherCompanyId=None,
                         xpathInternationalSecurIdentifier=None,
                         xpathLegalEntityIdentifier=None,
                         xpathSWIFT=None):

        try:
            temp = self.overview['identifiers']
        except:
            temp = {}

        if xpathTradeRegistry:
            trade = self.get_by_xpath(xpathTradeRegistry)
            if trade:
                temp['trade_register_number'] = trade[0]
        if xpathOtherCompanyId:
            other = self.get_by_xpath(xpathOtherCompanyId)
            if other:
                temp['other_company_id_number'] = other[0]
        if xpathInternationalSecurIdentifier:
            el = self.get_by_xpath(xpathInternationalSecurIdentifier)
            if el:
                temp['international_securities_identifier'] = el[0]
        if xpathLegalEntityIdentifier:
            el = self.get_by_xpath(xpathLegalEntityIdentifier)
            if el:
                temp['legal_entity_identifier'] = el[0]
        if xpathSWIFT:
            el = self.get_by_xpath(xpathSWIFT)
            if el:
                temp['swift_code'] = el[0]

        if temp:
            self.overview['identifiers'] = temp

    def fillField(self, fieldName, key=None, xpath=None, test=False, reformatDate=None):
        if xpath:
            el = self.get_by_xpath(xpath)
        if key:
            el = self.get_by_api(key)
        if test:
            print(el)
        if el:
            if len(el) == 1:
                el = el[0]
            if fieldName == 'vcard:organization-name':
                self.overview[fieldName] = el.split('(')[0].strip()

            if fieldName == 'hasActivityStatus':
                self.overview[fieldName] = el

            if fieldName == 'bst:registrationId':
                if type(el) == list:
                    el = ' '.join(el)
                el = ''.join(el.split('Registered Charity Number: ')[1]).split(' ')[0]
                if el:
                    self.overview[fieldName] = el.replace('\n', '')

            if fieldName == 'Service':
                self.overview[fieldName] = {'serviceType': el}

            if fieldName == 'regExpiryDate':
                el = el.split(' ')[0]
                self.overview[fieldName] = self.reformat_date(el, reformatDate) if reformatDate else el

            if fieldName == 'vcard:organization-tradename':
                self.overview[fieldName] = el.split('\n')[0].strip()

            if fieldName == 'bst:aka':
                names = el.split('\n')
                names = el.split(' D/B/A ')
                if len(names) > 1:
                    names = [i.strip() for i in names]
                    self.overview[fieldName] = names
                else:
                    self.overview[fieldName] = names

            if fieldName == 'lei:legalForm':
                self.overview[fieldName] = {
                    'code': el,
                    'label': ''}

            if fieldName == 'identifiers':
                self.overview[fieldName] = {
                    'other_company_id_number': el
                }
            if fieldName == 'map':
                self.overview[fieldName] = el[0] if type(el) == list else el

            if fieldName == 'dissolutionDate':
                self.overview[fieldName] = el

            if fieldName == 'previous_names':
                el = el.strip()
                el = el.split('\n')
                if len(el) < 1:
                    self.overview[fieldName] = {'name': [el[0].strip()]}
                else:
                    el = [i.strip() for i in el]
                    res = []
                    for i in el:
                        temp = {
                            'name': i
                        }
                        res.append(temp)
                    self.overview[fieldName] = res

            if fieldName == 'isIncorporatedIn':
                if reformatDate:
                    self.overview[fieldName] = self.reformat_date(el, reformatDate)
                else:
                    self.overview[fieldName] = el

            if fieldName == 'sourceDate':
                self.overview[fieldName] = self.reformat_date(el, '%d.%m.%Y')

            if fieldName == 'bst:description':
                if type(el) == list:
                    self.overview[fieldName] = ' '.join(el)
                else:
                    self.overview[fieldName] = el

            if fieldName == 'hasURL' and el != 'http://':
                self.overview[fieldName] = el

            if fieldName == 'tr-org:hasRegisteredPhoneNumber':
                if type(el) == list and len(el) > 1:
                    el = el[0]
                self.overview[fieldName] = el
                # print(self.get_address(returnAddress=True, addr=' '.join(el.split('\n')[1:]),
                # zipPattern='[A-Z]\d[A-Z]\s\d[A-Z]\d'))
            if fieldName == 'logo':
                self.overview['logo'] = el
            if fieldName == 'bst:email':
                self.overview['bst:email'] = el
            if fieldName == 'registeredIn':
                self.overview['registeredIn'] = el
            if fieldName == 'hasRegisteredFaxNumber':
                self.overview['hasRegisteredFaxNumber'] = el

    def check_tree(self):
        print(self.tree.xpath('//text()'))

    def get_working_tree_api(self, link_name, type, method='GET', data=None):
        if type == 'tree':
            if data:
                self.tree = self.get_tree(link_name,
                                          headers=self.header, method=method, data=json.dumps(data))
            else:
                self.tree = self.get_tree(link_name,
                                          headers=self.header, method=method)
        if type == 'api':
            self.api = self.get_content(link_name,
                                        headers=self.header, method=method, data=data)
            self.api = json.loads(self.api.content)

    def removeQuotes(self, text):
        text = text.replace('"', '')
        return text

    def get_overview(self, link_name):

        self.overview = {}

        self.overview['isDomiciledIn'] = 'US'


        self.overview['@source-id'] = self.NICK_NAME
        self.overview['bst:sourceLinks'] = ['https://portal.ct.gov/-/media/CID/1_Lists/Licencom.pdf']
        self.overview['bst:registryURI'] = 'https://portal.ct.gov/-/media/CID/1_Lists/Licencom.pdf'


        self.overview['vcard:organization-name'] = link_name.split('=?')[0]
        self.overview['registeredIn'] = link_name.split('=?')[2]
        self.overview['bst:businessClassifier'] = [{
            'code': link_name.split('=?')[1],
            'description': link_name.split('=?')[4],
            'label': 'NAIC'
        }]
        self.overview['regulator_name'] = 'Connecticut Insurance Department'
        self.overview['identifiers'] = {
            'other_company_id_number': link_name.split('=?')[1]
        }
        self.overview['regulator_url'] = self.base_url
        self.overview['RegulationStatus'] = 'Authorised'

        #
        #
        #
        # try:
        #     self.fillField('vcard:organization-name', xpath='//div[@class="legal-entity-name-container"]//h1/text()')
        # except:
        #     return None
        #
        #
        # self.fillField('hasActivityStatus',
        #                xpath='//div/text()[contains(., "Entity status")]/../following-sibling::div[2]/text()')
        #
        # # regID = self.get_by_xpath('//div/text()[contains(., "Registration ID")]/../following-sibling::div[1]/text()')[0]
        # # print(regID)
        # # self.getSpecialAddress()
        #
        # self.fillField('bst:description',
        #                xpath='//div[@class="seo-block margin-top-40"]/div/div//text()')
        #
        # self.fill_identifiers(
        #     xpathLegalEntityIdentifier='//span/text()[contains(., "LEI code")]/../following-sibling::span[1]/text()',
        #     xpathTradeRegistry='//div/text()[contains(., "Registration ID")]/../following-sibling::div[1]/text()',
        #     xpathSWIFT='//span[@class="bic-code-item"]/text()')
        #
        # self.fillField('regExpiryDate',
        #                xpath='//div/text()[contains(., "Next renewal date")]/../following-sibling::div[1]/text()',
        #                reformatDate='%Y/%m/%d')
        #
        # self.fillField('lei:legalForm',
        #                xpath='//div/text()[contains(., "Legal form")]/../following-sibling::div[1]/text()')
        #
        # self.overview['sourceDate'] = datetime.datetime.today().strftime('%Y-%m-%d')
        #
        # url = 'https://lei.info/externalData/openCorporates'
        #
        # data = {
        #     'companyIdentifier': self.overview['identifiers']['trade_register_number'],
        #     'jurisdictionCode': ''
        # }
        #
        # self.get_working_tree_api(url, type='api', data=data, method='POST')
        #
        # self.tree = etree.HTML(self.api['data'])
        #
        # self.getSpecialAddress()
        #
        # self.fillField('dissolutionDate',
        #                xpath='//div/text()[contains(., "Dissolution date")]/../following-sibling::div[1]/text()')
        # self.fillField('isIncorporatedIn',
        #                xpath='//div/text()[contains(., "Incorporation date")]/../following-sibling::div[1]/text()')
        #
        # agent = self.get_by_xpath('//div/text()[contains(., "Agent name")]/../following-sibling::div[1]/text()')
        # if agent:
        #     self.overview['agent'] = {
        #         '@type': 'Organization',
        #         'name': agent[0]
        #     }

        # self.fillField('logo', xpath='//div[@class="charity-logo"]/a/img/@src')
        # 'url'
        #
        # self.fillField('hasURL',
        #                xpath='//span[@itemprop="url"]/a/@href')
        #
        # self.fillField('bst:email',
        #                xpath='//span[@itemprop="email"]/text()')
        #
        # self.getSpecialAddress()
        #
        # self.fillField('registeredIn', xpath='//div[@class="charity-hgroup"]//text()[2]')
        #
        # self.fillField('tr-org:hasRegisteredPhoneNumber', xpath='//span[@itemprop="tel"]/text()')
        # self.fillField('hasRegisteredFaxNumber', xpath='//span[@itemprop="fax"]/text()')
        #
        # self.fillField('bst:registrationId',
        #                xpath='//div[@class="charity-hgroup"]//text()[1]')

        # if self.overview['bst:registrationId']:

        # print(self.overview)
        # exit()
        #
        # self.overview['bst:businessClassifier'] = [
        #     {
        #         "code": '',
        #         "description": link_name.split('?=')[-1],
        #         "label": ''
        #     }
        # ]
        # self.overview['bst:sourceLinks'] = ['https://naicom.gov.ng/insurance-industry/composite-companies/',
        #                                     'https://naicom.gov.ng/insurance-industry/general-companies/',
        #                                     'https://naicom.gov.ng/insurance-industry/life-companies/',
        #                                     'https://naicom.gov.ng/insurance-industry/takaful-companies/',
        #                                     'https://naicom.gov.ng/insurance-industry/re-insurance-companies/',
        #                                     'https://naicom.gov.ng/insurance-industry/licensed-brokers-companies/',
        #                                     'https://naicom.gov.ng/insurance-industry/loss-adjusters-companies/',
        #                                     'https://naicom.gov.ng/insurance-industry/micro-insurance/']
        #
        # self.overview['regulator_name'] = 'National Insurance Commission'
        # self.overview['regulatorAddress'] = {
        #     'fullAddress': 'Plot 1239, Ladoke Akintola Boulevard, Garki II Abuja',
        #     'city': 'Abuja',
        #     'country': 'Naigeria'
        # }
        # self.overview['regulator_url'] = 'https://naicom.gov.ng/about-us/'
        # self.overview['RegulationStatus'] = 'Authorised'
        #
        # self.get_address(addr=link_name.split('?=')[1])

        # self.fillField('bst:aka',
        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Contact Information")]/../following-sibling::div[1]//tr[1]/td[2]/text()')
        #
        # self.get_address(
        #     xpath='//div[@class="sectionHeader"]/text()[contains(., "Address")]/../following-sibling::div[1]//text()',
        #     zipPattern='\d\d\d\d\d+')

        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Contact")]/../following-sibling::div[1]//td//text()[contains(., "Business Phone")]/../following-sibling::td[1]/text()')
        # self.fillField('bst:description',
        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Purpose")]/../following-sibling::div[1]/text()')
        # self.overview['registeredIn'] = 'Mississippi'
        #
        # self.fillField('identifiers',
        #                xpath='//div[@class="sectionHeader"]/text()[contains(., "Filing Information")]/../following-sibling::div[1]//td/text()[contains(., "Filing Number")]/../following-sibling::td/text()')
        # if self.overview['bst:registrationId']:
        #     self.overview['bst:registrationId'] = self.overview['bst:registrationId']
        # self.overview['regulator_name'] = 'Michal watson - Mississippi Secretary of State'
        # self.overview['regulatorAddress'] = {
        #     'fullAddress': 'New Capitol Room 105 Jackson, Mississippi 39201, United state',
        #     'city': 'Jackson',
        #     'country': 'United States'
        # }
        # self.overview['regulator_url'] = 'https://www.sos.ms.gov/contact-us/capitol-office'
        # self.overview['RegulationStatus'] = 'Active'

        # self.overview['Service'] = {
        #     'areaServed': 'Mississippi',
        #     'serviceType': 'charity'
        # }
        #
        # self.overview['@source-id'] = self.NICK_NAME
        # print(self.overview)
        # exit()

        # print(self.overview)
        # exit()
        # # self.overview['bst:sourceLinks'] = link_name
        #
        # self.fillField('vcard:organization-tradename', key='Trade Name(s)')

        # self.fillField('previous_names', key='Former Name(s)')

        #
        # self.fillField('Service', key='Business In')
        # self.fillField('agent', key='Chief Agent')
        # self.fillField('previous_names', key='Former Name(s)')
        # self.fillField('regExpiryDate', key='Expiry Date', reformatDate='%d-%b-%Y')
        # self.overview[
        #     'bst:registryURI'] = f'https://www.princeedwardisland.ca/en/feature/pei-business-corporate-registry-original#/service/LegacyBusiness/LegacyBusinessView;e=LegacyBusinessView;business_number={self.api["Registration Number"]}'
        # self.overview['@source-id'] = self.NICK_NAME

        # print(self.overview)
        # exit()
        # self.fillField('lei:legalForm', '//div/text()[contains(., "Legal form")]/../following-sibling::div//text()')
        # self.fillField('identifiers', '//div/text()[contains(., "Registry code")]/../following-sibling::div//text()')
        # self.fillField('map', '//div/text()[contains(., "Address")]/../following-sibling::div/a/@href')
        # self.fillField('incorporationDate', '//div/text()[contains(., "Registered")]/../following-sibling::div/text()')

        # self.fillField('bst:businessClassifier', '//div/text()[contains(., "EMTAK code")]/../following-sibling::div/text()')
        # self.get_business_class('//div/text()[contains(., "EMTAK code")]/../following-sibling::div/text()',
        #                         '//div/text()[contains(., "Area of activity")]/../following-sibling::div/text()',
        #                         '//div/text()[contains(., "EMTAK code")]/../following-sibling::div/text()')
        #
        # self.get_address('//div/text()[contains(., "Address")]/../following-sibling::div/text()',
        #                  zipPattern='\d{5}')
        #
        #

        # self.overview['@source-id'] = self.NICK_NAME

        # print(self.overview)
        return self.overview

    # def get_officership(self, link_name):
    #     self.get_working_tree_api(link_name, 'api')
    #
    #     names = self.get_by_api('Officer(s)')
    #     if '\n' in names:
    #         names = names.split('\n')
    #     # roles = self.get_by_xpath(
    #     #     '//div/text()[contains(., "Right of representation")]/../following-sibling::div//tr/td[3]/text()')
    #
    #     off = []
    #     names = [names] if type(names) == str else names
    #     roles = []
    #     for name in names:
    #         roles.append(name.split(' - ')[-1])
    #     names = [i.split(' - ')[0] for i in names]
    #
    #     # roles = [roles] if type(roles) == str else roles
    #     for n, r in zip(names, roles):
    #         home = {'name': n,
    #                 'type': 'individual',
    #                 'officer_role': r,
    #                 'status': 'Active',
    #                 'occupation': r,
    #                 'information_source': self.base_url,
    #                 'information_provider': 'Prince Edward Island Corporate Registry'}
    #         off.append(home)
    #     return off

    # def get_documents(self, link_name):
    #     docs = []
    #     self.get_working_tree(link_name)
    #     docs_links = self.get_by_xpath('//div/a/text()[contains(., "PDF")]/../@href')
    #     docs_links = docs_links if type(docs_links) == list else [docs_links]
    #     docs_links = [f'{self.base_url}{i}' for i in docs_links]
    #     for doc in docs_links:
    #         temp = {
    #             'url': doc,
    #             'description': 'Summary of company details'
    #         }
    #         docs.append(temp)
    #     return docs

    # def get_financial_information(self, link_name):
    #     self.get_working_tree(link_name)
    #     fin = {}
    #     summ = self.get_by_xpath('//div/text()[contains(., "Capital")]/../following-sibling::div//text()')
    #     if summ:
    #         summ = re.findall('\d+', summ[0])
    #         if summ:
    #             fin['Summary_Financial_data'] = [{
    #                 'summary': {
    #                     'currency': 'Euro',
    #                     'balance_sheet': {
    #                         'authorized_share_capital': ''.join(summ)
    #                     }
    #                 }
    #             }]
    #     return fin
    # def get_shareholders(self, link_name):
    #
    #     edd = {}
    #     shareholders = {}
    #     sholdersl1 = {}
    #
    #     company = self.get_overview(link_name)
    #     company_name_hash = hashlib.md5(company['vcard:organization-name'].encode('utf-8')).hexdigest()
    #     self.get_working_tree_api(link_name, 'api')
    #     # print(self.api)
    #
    #     try:
    #         names = self.get_by_api('Shareholder(s)')
    #         if len(re.findall('\d+', names)) > 0:
    #             return edd, sholdersl1
    #         if '\n' in names:
    #             names = names.split('\n')
    #
    #         holders = [names] if type(names) == str else names
    #
    #         for i in range(len(holders)):
    #             holder_name_hash = hashlib.md5(holders[i].encode('utf-8')).hexdigest()
    #             shareholders[holder_name_hash] = {
    #                 "natureOfControl": "SHH",
    #                 "source": 'Prince Edward Island Corporate Registry',
    #             }
    #             basic_in = {
    #                 "vcard:organization-name": holders[i],
    #                 'isDomiciledIn': 'CA'
    #             }
    #             sholdersl1[holder_name_hash] = {
    #                 "basic": basic_in,
    #                 "shareholders": {}
    #             }
    #     except:
    #         pass
    #
    #     edd[company_name_hash] = {
    #         "basic": company,
    #         "entity_type": "C",
    #         "shareholders": shareholders
    #     }
    #     # print(sholdersl1)
    #     return edd, sholdersl1

    # def get_financial_information(self, link):
    #     data = {
    #         "searchType": "Charity_Services_IFSSearchResults",
    #         "entityName": link,
    #         "fileNumber": "",
    #         "filingClassId": "00000000-0000-0000-0000-000000000000"
    #     }
    #     url = 'https://charities.sos.ms.gov/online/Services/Common/IFSServices.asmx/ExecuteSearch'
    #     self.get_working_tree_api(url, 'api', method='POST', data=data)
    #     g = self.api['d']
    #     d = json.loads(g)
    #     self.api = d['Table'][0]
    #     url = f'https://charities.sos.ms.gov/online/portal/ch/page/charities-search/~/ViewXSLTFileByName.aspx?providerName=CH_EntityBasedFilingDetails&FilingId={self.api["FilingId"]}'
    #     self.get_working_tree_api(url, 'tree')
    #
    #     period = self.get_by_xpath(
    #         '//div[@class="sectionHeader"]/text()[contains(., "Financial Information")]/../following-sibling::div/div/text()')
    #     revenue = self.get_by_xpath(
    #         '//div[@class="sectionHeader"]/text()[contains(., "Financial Information")]/../following-sibling::div/div//td/text()[contains(., "Total Revenue")]/../following-sibling::td/text()')
    #     temp = {}
    #     if period and revenue:
    #         period = [self.reformat_date(i.split(': ')[-1], '%m/%d/%Y') for i in period]
    #         revenue = [i[2:] for i in revenue]
    #         tempList = []
    #         for p, r in zip(period, revenue):
    #             tempList.append({
    #                 'period': p,
    #                 'revenue': r
    #             })
    #
    #         temp['Summary_Financial_data'] = [{
    #             'source': 'Michael Watson Secretory of state',
    #             'summary': {
    #                 'currency': 'USD',
    #                 'income_statement': tempList[0]
    #             }
    #         }]
    #     # print(temp)
    #     return temp

    # def get_financial_information(self, link_name):
    #     self.get_working_tree_api(link_name, 'tree')
    #     self.check_tree()
    #     print(link_name)
    #
    #
    #
    #
    #     fin = {}
    #
    #     finInfo = self.get_by_xpath('//div[@class="container financial-information-block"]//text()')
    #     if finInfo:
    #         cur = self.get_by_xpath('//div[@class="container financial-information-block"]/div[2]/div[2]/text()')
    #         period = self.get_by_xpath('//div[@class="container financial-information-block"]/div[1]/div[2]/text()')
    #         cur2 = self.get_by_xpath('//div[@class="container financial-information-block"]/div[2]/div[3]/text()')
    #
    #         temp = {
    #             'source': link_name,
    #             'inner_source': '',
    #
    #         }
    #         try:
    #             if period:
    #                 period = period[0][-4:]
    #                 period = f'"{period}-01-01"-"{period}-12-31"'
    #             if cur:
    #                 tempInner = {
    #                     'currency': cur[0][0],
    #                     'income_statement': {
    #                         'period': period,
    #                         'revenue': str(int(cur[0][1:].replace(',','')) + int(cur2[0][1:].replace(',','')))
    #                     }
    #                 }
    #
    #
    #             if tempInner:
    #                 temp['summary'] = tempInner
    #         except:
    #             pass
    #
    #     fin['Summary_Financial_data'] = [temp]
    #     #
    #     # temp = {
    #     #     'stock_id': ''
    #     # }
    #     #
    #     # try:
    #     #     temp['stock_name'] = ''
    #     # except:
    #     #     pass
    #     #
    #     # curr = {
    #     #     'data_date': datetime.datetime.strftime(datetime.datetime.today(), '%Y-%m-%d')
    #     # }
    #     # # open = self.get_by_xpath('//td//text()[contains(., "Open price")]/../following-sibling::td//text()')
    #     # if open:
    #     #     curr['open_price'] = str(self.api['OpenPrice'])
    #     #
    #     # # min = self.get_by_xpath('//td//text()[contains(., "Low price")]/../following-sibling::td//text()')
    #     # # max = self.get_by_xpath('//td//text()[contains(., "High price")]/../following-sibling::td//text()')
    #     # min = self.api['DaysLow']
    #     # max = self.api['DaysHigh']
    #     #
    #     # if min and max:
    #     #     curr['day_range'] = f'{min}-{max}'
    #     #
    #     # # vol = self.get_by_xpath('//td//text()[contains(., "Total no. of shares")]/../following-sibling::td//text()')
    #     # vol = self.api['Volume']
    #     # if vol:
    #     #     curr['volume'] = str(vol)
    #     #
    #     # # prClose= self.get_by_xpath('//td//text()[contains(., "Last price")]/../following-sibling::td//text()')
    #     # prClose = self.api['PrevClose']
    #     # if prClose:
    #     #     curr['prev_close_price'] = str(prClose)
    #     #
    #     # # cap = self.get_by_xpath('//td//text()[contains(., "Market cap")]/../following-sibling::td//text()')
    #     # cap = self.api['MarketCap']
    #     # if cap:
    #     #     curr['market_capitalization'] = str(cap)
    #     #
    #     # curr['exchange_currency'] = 'naira'
    #     #
    #     # # min52 = self.get_by_xpath('//td//text()[contains(., "52 weeks low")]/../following-sibling::td//text()')
    #     # # max52 = self.get_by_xpath('//td//text()[contains(., "52 weeks high")]/../following-sibling::td//text()')
    #     # min52 = self.api['LOW52WK_PRICE']
    #     # max52 = self.api['HIGH52WK_PRICE']
    #     # if min52 and max52:
    #     #     curr['52_week_range'] = f'{min52}-{max52}'
    #     #
    #     # temp['current'] = curr
    #     # fin['stocks_information'] = [temp]
    #     #
    #     # # summ = self.get_by_xpath('//div/text()[contains(., "Capital")]/../following-sibling::div//text()')
    #     #
    #     # # if summ:
    #     # #     summ = re.findall('\d+', summ[0])
    #     # #     if summ:
    #     # fin['Summary_Financial_data'] = [{
    #     #     'summary': {
    #     #         'currency': 'naira',
    #     #         'balance_sheet': {
    #     #             'market_capitalization': str(self.api['MarketCap'])
    #     #         }
    #     #     }
    #     # }]
    #     # self.get_working_tree_api(
    #     #     f'https://ngxgroup.com/exchange/data/company-profile/?isin={self.api["InternationSecIN"]}&directory=companydirectory',
    #     #     'tree')
    #     #
    #     # res = []
    #     # dates = self.tree.xpath(
    #     #     '//h3/text()[contains(., "Last 7 Days Trades")]/../../following-sibling::div[1]//tr/td[1]/text()')[:-1]
    #     # prices = self.tree.xpath(
    #     #     '//h3/text()[contains(., "Last 7 Days Trades")]/../../following-sibling::div[1]//tr/td[2]/text()')[:-1]
    #     # volumes = self.tree.xpath(
    #     #     '//h3/text()[contains(., "Last 7 Days Trades")]/../../following-sibling::div[1]//tr/td[3]/text()')[:-1]
    #     # prPrices = prices[1:]
    #     #
    #     # for d, p, v, pr in zip(dates, prices, volumes, prPrices):
    #     #     res.append(
    #     #         {
    #     #             'data_date': datetime.datetime.strftime(datetime.datetime.today(), '%Y-%m-%d'),
    #     #             'open_price': pr,
    #     #             'close_price': p,
    #     #             'volume': v,
    #     #             'day_range': f'{pr}-{p}',
    #     #         }
    #     #     )
    #     # fin['stocks_information'].append({'historical_prices': res})
    #
    #     return fin
