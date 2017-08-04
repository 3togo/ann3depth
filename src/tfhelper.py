import functools
import tensorflow as tf


def create_reset_metric(metric, scope, **metric_args):
    """Creates a ops to handle streaming metrics.

    This is a wrapper function to create a streaming metric (usually
    tf.contrib.metrics.streaming_*) with a reset operation.

    Args:
        metric: The metric function
        scope: The variable scope name (should be unique, as the variables of
               this scope will be reset every time the reset op is evaluated)
        metric_args: The arguments to be passed on to the metric.

    Returns:
        Three ops: the metric read_out op, the update op and the reset op:
            metric_op, update_op, reset_op
    """
    with tf.variable_scope(scope) as scope:
        metric_op, update_op = metric(**metric_args)
        vars = tf.contrib.framework.get_variables(
            scope, collection=tf.GraphKeys.LOCAL_VARIABLES)
        reset_op = tf.variables_initializer(vars)
    return metric_op, update_op, reset_op


def make_template(scope=None, create_scope_now_=False, unique_name_=None,
                  custom_getter_=None, **kwargs):
    """A decorator to map a function as a tf template using tf.make_template.

    This enables variable sharing between multiple instances of that function.

    Args:
        scope: The scope for this template. Defaults to the function name.
        create_scope_now_: Passed to the tf.make_template function.
        unique_name_: Passed to the tf.make_template function.
        custom_getter_: Passed to the tf.make_template function.
        kwargs: Passed to the tf.make_template function.

    Returns:
        The function wrapped inside a tf.make_template.
    """
    def make_tf_template(function):
        template = tf.make_template(function.__name__
                                    if scope is None or callable(scope)
                                    else scope,
                                    function,
                                    create_scope_now_=create_scope_now_,
                                    unique_name_=unique_name_,
                                    custom_getter_=custom_getter_,
                                    **kwargs)

        @functools.wraps(function)
        def wrapper(*caller_args, **caller_kwargs):
            return template(*caller_args, **caller_kwargs)
        return wrapper


def with_scope(scope):
    """A decorator to wrap a function into a tf.name_scope.

    Args:
        scope: The scope name.

    Returns:
        The wrapped function.
    """
    def add_scope(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            with tf.name_scope(scope):
                return function(*args, **kwargs)
        return wrapper
    return add_scope
