"""
This command generates enrollment codes for courses.
"""
import copy
from datetime import datetime

from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from django.db import transaction
from ecommerce.core.models import User
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.partner.strategy import DefaultStrategy
from oscar.core.loading import get_class, get_model

Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BasketLine = get_model('basket', 'Line')
Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
Partner = get_model('partner', 'Partner')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentEventTypeName = get_class('order.constants', 'PaymentEventTypeName')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
PaymentSource = get_model('payment', 'Source')
PaymentSourceType = get_model('payment', 'SourceType')
Product = get_model("catalogue", "Product")
ProductClass = get_model("catalogue", "ProductClass")
StockRecord = get_model('partner', 'StockRecord')


class CreatePurchaseError(Exception):
    """
    Exception raised when an error occurs while creating a purchase.
    """


class CreatePurchaseDryRunException(Exception):
    """
    Exception raised when a dry run is performed.
    """


class Command(BaseCommand):
    """
    Creates enrollment codes for courses.
    """

    help = 'Create a course purchase for a user.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--site-domain',
            action='store',
            dest='site-domain',
            default=None,
            help='Domain of the site where the purchase is being made.',
            type=str,
            required=True,
        )
        parser.add_argument(
            '--course-id',
            action='store',
            dest='course_id',
            default=None,
            help='Course ID to be purchased for the user.',
            type=str,
            required=True,
        )
        parser.add_argument(
            '--sku',
            action='store',
            dest='sku',
            default=None,
            help='SKU of the course to be purchased.',
            type=str,
            required=True,
        )
        parser.add_argument(
            '--lms-user-id',
            action='store',
            dest='lms_user_id',
            default=None,
            help='ID of the user who will purchase the course as in LMS.',
            type=str,
            required=True,
        )
        parser.add_argument(
            '--amount',
            action='store',
            dest='amount',
            default=None,
            help='Purchase amount for the course.',
            type=float,
        )
        parser.add_argument(
            '--commit',
            action='store',
            dest='commit',
            default='no',
            help='Commit changes, default is no (just perform a dry-run).',
            type=str,
        )
        parser.add_argument(
            '--note',
            action='store',
            dest='note',
            default=None,
            help='Note to be added to the purchase.',
            type=str,
        )
        parser.add_argument(
            '--submit-date',
            action='store',
            dest='submit_date',
            default=None,
            help='Date when the purchase is submitted.',
            type=str,
        )

    def __init__(self):
        super().__init__()

        self.lms_user_id = None
        self.options = None
        self.site = None
        self.partner = None
        self.course_id = None
        self.amount = None
        self.user = None
        self.note = None
        self.submit_date = None
        self.product = None
        self.sku = None
        self.stock_record = None
        self.currency = None
        self.commit = False
        self._confirmation_message = None

    def parse_options(self, options):
        """
        Parse the options passed to the command.
        """
        site_domain = options['site-domain']
        try:
            self.site = Site.objects.get(domain=site_domain)
        except Site.DoesNotExist:
            raise CreatePurchaseError(f'Site with domain {site_domain} does not exist.')

        try:
            self.partner = Partner.objects.get(default_site_id=self.site.id)
        except Partner.DoesNotExist:
            raise CreatePurchaseError(f'Partner with default site ID {self.site.id} does not exist.')

        self.sku = options['sku']
        self.course_id = options['course_id']
        self.product = self.get_product()

        try:
            self.stock_record = StockRecord.objects.get(
                product=self.product,
                partner=self.partner,
                partner_sku=self.sku,
            )
        except StockRecord.DoesNotExist:
            raise CreatePurchaseError(f'Stock record for product {self.product.id} with SKU {self.sku} does not exist.')
        self.currency = self.stock_record.price_currency
        if self.currency != 'SAR':
            raise CreatePurchaseError(f'Currency {self.currency} of stock record {self.stock_record.id }is not supported.')

        if options['amount']:
            try:
                self.amount = float(options['amount'])
            except ValueError:
                raise CreatePurchaseError('Invalid amount format. Use a number.')
        else:
            self.amount = self.get_amount()
        if self.amount <= 0:
            raise CreatePurchaseError('Amount must be greater than 0.')

        self.lms_user_id = options['lms_user_id']
        self.user = self.get_user()

        self.note = options['note']

        try:
            if options['submit_date']:
                self.submit_date = datetime.strptime(options['submit_date'], '%Y-%m-%d')
            else:
                self.submit_date = datetime.now()
        except ValueError:
            raise CreatePurchaseError('Invalid submit date format. Use YYYY-MM-DD.')

        if options['commit']:
            self.commit = (options['commit'].lower() == 'yes')

    def get_confirmation_message(self):
        if not self._confirmation_message:
            self._confirmation_message = (
                "You are about to manually create a purchase order with it's payment. Here are the details:\n\n"
                f"user ID in LMS: {self.lms_user_id}\n"
                f"user ID in ecommerce: {self.user.id}\n"
                f"username in ecommerce: {self.user.username}\n"
                f"user email in ecommerce: {self.user.email}\n"
                f"course id: {self.course_id}\n"
                f"site: {self.site}\n"
                f"SKU: {self.sku}\n"
                f"price: {self.amount}\n"
                f"currency: {self.currency}\n"
                f"invoice date: {self.submit_date}\n"
                f"admin note: {self.note}\n\n"
                "Would you like to create the purchase? (yes/No): "
            )

        return self._confirmation_message

    def handle(self, *args, **options):
        import warnings

        self.options = copy.deepcopy(options)
        try:
            warnings.filterwarnings("ignore")
            print('-' * 80)
            print('Parsing options...')
            self.parse_options(options)
            print('Options parsed successfully.')

            print('Verifying that no previous order already exists...')
            order_details = self.get_order_details(self.course_id, self.user)
            if order_details:
                raise CreatePurchaseError(f'Order already exists: {order_details}')
            print('Greate, no order exists.')

            if self.commit:
                print('-' * 20, ' confirmation! ', '-' * 20)
                confirm = input(self.get_confirmation_message()).lower()
                if confirm != 'yes':
                    raise CreatePurchaseError('Operation canceled by user, nothing changed.')

            with transaction.atomic():
                print('Creating basket...')
                basket = self.create_basket()
                print('Creating order...')
                order = self.create_order(basket)
                print('Creating payment...')
                self.create_payment(order, basket)
                if not self.commit:
                    raise CreatePurchaseDryRunException()

                print('Purchase created successfully!')
                print(f'Order number: {order.number}')

        except CreatePurchaseDryRunException:
            print('Dry run completed successfully!')

        except CreatePurchaseError as e:
            print(f'ERROR: {str(e)}')

        except Exception as e:
            print('ERROR: unexpected failure')
            raise e
        finally:
            print('-' * 80)
            warnings.filterwarnings("default")

    def get_user(self):
        """
        Verify if the user exists in LMS.
        """
        if not self.lms_user_id:
            raise CreatePurchaseError('LMS user ID is required.')

        try:
            user = User.objects.get(lms_user_id=self.lms_user_id)
        except User.DoesNotExist:
            raise CreatePurchaseError(f'User with LMS ID {self.lms_user_id} does not exist.')
        except User.MultipleObjectsReturned:
            raise CreatePurchaseError(f'Multiple users with LMS ID {self.lms_user_id} exist.')

        return user

    def get_order_details(self, course_id, user):
        """
        Get the order details for the course purchase.
        """
        result = Order.objects.filter(
            user=self.user,
            site=self.site,
            lines__product__course_id=self.course_id,
            lines__stockrecord__partner=self.partner,
        ).values('id', 'number', 'date_placed', 'total_incl_tax').first()

        return None if result is None else {
            'id': result['id'],
            'number': result['number'],
            'date_placed': str(result['date_placed']),
            'total_incl_tax': float(result['total_incl_tax']),
        }

    def get_product(self):
        """
        Verify if the course exists.
        """
        try:
            product_class = ProductClass.objects.get(slug='seat')
        except ProductClass.DoesNotExist:
            raise CreatePurchaseError('Product class "seat" does not exist.')

        try:
            product = Product.objects.get(course_id=self.course_id, product_class=product_class)
        except Product.DoesNotExist:
            raise CreatePurchaseError(f'Course with ID {self.course_id} does not exist in products.')
        except Product.MultipleObjectsReturned:
            raise CreatePurchaseError(f'Multiple products with ID {self.course_id} exist.')

        product_children = Product.objects.filter(course_id=self.course_id, parent_id=product.id)
        if product_children.count() > 1:
            raise CreatePurchaseError(f'Too many product options for the course with ID {self.course_id}.')

        return product if product_children.count() == 0 else product_children.first()

    def get_amount(self):
        """
        Get the amount for the course purchase.
        """
        result = self.stock_record.price_retail
        if not result:
            raise CreatePurchaseError(
                f'Price for stock record {self.stock_record.id} is not set. Please fill it or pass --amount=<price>'
            )

    def create_basket(self):
        """
        Create a basket for the course purchase.
        """
        basket = Basket.objects.create(
            status=Basket.OPEN,
            date_created=self.submit_date,
            date_submitted=self.submit_date,
            owner=self.user,
            site=self.site,
        )
        BasketAttribute.objects.create(
            value_text=False,
            attribute_type=BasketAttributeType.objects.get(id=1),  # email_opt_in
            basket=basket,
        )
        BasketLine.objects.create(
            line_reference=f'{self.product.id}-{self.stock_record.id}',
            quantity=1,
            price_currency=self.currency,
            price_excl_tax=self.amount,
            price_incl_tax=self.amount,
            date_created=self.submit_date,
            basket=basket,
            product=self.product,
            stockrecord=self.stock_record,
            date_updated=self.submit_date,
        )
        basket.status = Basket.SUBMITTED
        basket.strategy = DefaultStrategy()
        basket.save()

        return basket

    def get_order_number(self, basket_id):
        if self.commit:
            return OrderNumberGenerator().order_number_from_basket_id(self.partner, basket_id)

        prefix = 'MANUAL-ENTRY-'
        digits = 6
        order = Order.objects.filter(number__startswith=prefix).order_by('-number').first()
        if not order:
            last_number = 0
        else:
            last_number = int(order.number[len(prefix):])

        return f'{prefix}{str(last_number + 1).zfill(digits)}'

    def create_order(self, basket):
        """
        Create an order for the course purchase.
        """
        order = Order.objects.create(
            basket=basket,
            number=self.get_order_number(basket.id),
            site=self.site,
            total_incl_tax=self.amount,
            total_excl_tax=self.amount,
            currency=self.currency,
            user=self.user,
            date_placed=self.submit_date,
            status=ORDER.COMPLETE,
        )
        line = OrderLine.objects.create(
            partner_name=self.partner.name,
            partner_sku=self.sku,
            title=self.product.title,
            quantity=1,
            line_price_excl_tax=self.amount,
            line_price_incl_tax=self.amount,
            line_price_before_discounts_excl_tax=self.amount,
            line_price_before_discounts_incl_tax=self.amount,
            unit_price_excl_tax=self.amount,
            unit_price_incl_tax=self.amount,
            status=ORDER.COMPLETE,
            order=order,
            partner=self.partner,
            product=self.product,
            stockrecord=self.stock_record,
        )
        line.prices.create(
            order=order,
            line=line,
            price_incl_tax=self.amount,
            price_excl_tax=self.amount,
            quantity=1,
        )
        return order

    def create_payment(self, order, basket):
        """
        Create a payment for the course purchase.
        """
        payment = PaymentEvent.objects.create(
            order=order,
            amount=self.amount,
            reference=order.number,
            event_type=PaymentEventType.objects.get(code=PaymentEventTypeName.PAID),
            date_created=self.submit_date,
            processor_name='manual_order',
        )
        payment.line_quantities.create(
            quantity=1,
            event=payment.id,
            line=order.lines.first(),
        )
        PaymentProcessorResponse.objects.create(
            processor_name='manual_order',
            transaction_id=order.number,
            response={
                'created_by': 'shell command create_course_purchase_for_user',
                'created_on': datetime.now().isoformat(),
                'command_options': self.options,
                'user_note': self.note,
                'admin_confirmation_msg': self.get_confirmation_message(),
            },
            created=self.submit_date,
            basket=basket,
        )
        PaymentSource.objects.create(
            currency=self.currency,
            amount_allocated=self.amount,
            amount_debited=self.amount,
            amount_refunded=0,
            reference=order.number,
            label='Manual Payment',
            order=order,
            source_type=PaymentSourceType.objects.get(code='manual'),
            card_type='manual',
        )
        return payment
