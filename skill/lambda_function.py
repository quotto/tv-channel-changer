# -*- coding: utf-8 -*-

import sys
import os
import logging
import traceback
import json
import time 
from uuid import uuid4

import ask_sdk_core.utils as ask_utils
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response

import pymysql
from awscrt import io,mqtt,auth,http 
from awsiot import mqtt_connection_builder

PATH_TO_CERT = "certificate/certificate.pem.crt"
PATH_TO_KEY = "certificate/private.pem.key"
PATH_TO_ROOT = "certificate/root.pem"
TOPIC = "tv_channel"
ENDPOINT = os.environ["ENDPOINT"]
CLIENT_ID = str(uuid4())

# Yahoo!番組表の放送局名とチャンネル番号を固定で紐付ける
CHANNEL = {"TBCテレビ1": 1, "NHKEテレ1仙台": 2, "NHK総合1・仙台": 3, "ミヤギテレビ": 4, "東日本放送CH1": 5, "仙台放送": 8}

# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    logger.error("Connection interrupted. error: {}".format(error))


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    logger.warn("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        logger.warn("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)

def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    logger.warn("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))


# Spin up resources
event_loop_group = io.EventLoopGroup(1)
host_resolver = io.DefaultHostResolver(event_loop_group)
client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "見たい番組名を言ってください"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class ChangeChannelIntentHndler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ChangeChannelIntent")(handler_input)
        
    def handle(self, handler_input):
        slot = ask_utils.request_util.get_slot(handler_input,"TVProgram")
        speak_output = "すみません、わかりませんでした"
        if(slot != None):
            speak_output = "{}です。".format(slot.value)
            connection=pymysql.connect(
                    user='myuser',
                    password='myuser',
                    host='35.232.73.25',
                    database='tvDB',
                    autocommit=False
                    )
            cursor=connection.cursor()
            try:
                    cursor.execute("select id,title,time,provider,match(title) against ('*D+ {0}' in boolean mode) as score from tv_program where match(title) against ('*D+ {0}' in boolean mode) > 0 order by score desc".format(slot.value))
                    result = cursor.fetchall()
                    logger.info(json.dumps(result))
                    if(len(result)>0):
                        provider = result[0][3]
                        if(provider != None and CHANNEL[provider] != None):
                            speak_output = speak_output + "放送局は{}です。".format(result[0][3])

                            # Publish message to server desired number of times.
                            logger.info('Begin Publish')
                            mqtt_connection = mqtt_connection_builder.mtls_from_path(
                                        endpoint=ENDPOINT,
                                        cert_filepath=PATH_TO_CERT,
                                        pri_key_filepath=PATH_TO_KEY,
                                        client_bootstrap=client_bootstrap,
                                        ca_filepath=PATH_TO_ROOT,
                                        on_connection_interrupted=on_connection_interrupted,
                                        on_connection_resumed=on_connection_resumed,
                                        client_id=CLIENT_ID,
                                        clean_session=False,
                                        keep_alive_secs=6,
                                        region="ap-northeast-1"
                                        )
                            logger.info("Connecting to {} with client ID '{}'...".format(
                                    ENDPOINT, CLIENT_ID))

                            # Make the connect() call
                            connect_future = mqtt_connection.connect()
                            # Future.result() waits until a result is available
                            connect_future.result()
                            logger.info("Connected!")

                            for i in range (3):
                                message = {"channel": CHANNEL[provider],"count": i+1}
                                mqtt_connection.publish(topic=TOPIC, payload=json.dumps(message), qos=mqtt.QoS.AT_LEAST_ONCE)
                                logger.info("Published: '" + json.dumps(message) + "' to the topic: " + TOPIC)
                                time.sleep(0.1)
                            logger.info('Publish End')
                            disconnect_future = mqtt_connection.disconnect()
                            disconnect_future.result()
                        else:
                            speak_output = speak_output + "放送局が見つかりませんでした"

                    else:
                        speak_output = speak_output + "放送局が見つかりませんでした。"
            except Exception as err:
                logger.error(traceback.format_exc())
            finally:
                if(cursor!=None):
                    cursor.close()
                    connection.close()
        return(
            handler_input.response_builder.speak(speak_output).response
            )



class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "You can say hello to me! How can I help?"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Goodbye!"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
                .speak(speak_output)
                # .ask("add a reprompt if you want to keep the session open for the user to respond")
                .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(ChangeChannelIntentHndler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler()) # make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()