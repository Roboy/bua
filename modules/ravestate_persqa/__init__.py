from ravestate.module import Module
from ravestate.property import PropertyBase
from ravestate.wrappers import ContextWrapper
from ravestate.state import state, Emit, Delete
from ravestate.constraint import s
from ravestate_verbaliser import verbaliser
import ravestate_ontology

from os.path import realpath, dirname, join
from typing import Dict
import random

from scientio.ontology.ontology import Ontology
from scientio.session import Session
from scientio.ontology.node import Node
from reggol import get_logger
logger = get_logger(__name__)

import ravestate_idle
import ravestate_nlp
import ravestate_rawio

verbaliser.add_folder(join(dirname(realpath(__file__)), "persqa_phrases"))

PREDICATE_SET = {"FROM", "HAS_HOBBY", "LIVE_IN", "FRIEND_OF", "STUDY_AT", "MEMBER_OF", "WORK_FOR", "OCCUPIED_AS"}
# TODO "movies", "OTHER"
# TODO "sex", "birth date", "full name"
# TODO "EQUALS"

with Module(name="persqa") as mod:

    subject = PropertyBase(
        name="subject",
        default_value="",
        always_signal_changed=True,
        allow_pop=False,
        allow_push=False,
        is_flag_property=True)

    predicate = PropertyBase(
        name="predicate",
        default_value="",
        always_signal_changed=True,
        allow_pop=False,
        allow_push=False,
        is_flag_property=True)

    answer = PropertyBase(
        name="answer",
        default_value="",
        always_signal_changed=True,
        allow_pop=False,
        allow_push=False,
        is_flag_property=True)


    @state(cond=s("interloc:all:pushed"),
           write="interloc:all",
           read="interloc:all",
           signal_name="new-interloc",
           emit_detached=True)
    def new_interloc(ctx: ContextWrapper):
        """
        reacts to interloc:pushed and creates persqa:ask_name state
        """
        interloc_path = ctx["interloc:all:pushed"]

        @state(cond=s("persqa:new-interloc", max_age=-1, detached=True),
               write=("rawio:out", "persqa:subject", "persqa:predicate"))
        def ask_name(ctx):
            """
            reacts to idle:bored & persqa:new-interloc
            asks for interlocutors name
            """
            ctx["persqa:predicate"] = "NAME"
            ctx["rawio:out"] = verbaliser.get_random_question("NAME")
            ctx["persqa:subject"] = interloc_path

        mod.add(ask_name)
        ctx.add_state(ask_name)
        return Emit()


    def find_empty_entry(dictonary: Dict):
        for key in dictonary:
            if not dictonary[key] and key in PREDICATE_SET:
                return key
        return None


    def create_small_talk_state(ctx: ContextWrapper, interloc_path: str):

        follow_ups = set()

        # TODO only trigger when also bored?
        @state(cond=s("idle:bored", max_age=-1, detached=True),
               write=("rawio:out", "persqa:predicate", "persqa:subject"),
               read="interloc:all")
        def small_talk(ctx: ContextWrapper):
            interloc: Node = ctx[interloc_path]
            relationships = interloc.get_relationships()
            key = find_empty_entry(relationships)
            if key:
                ctx["persqa:predicate"] = key
                output = verbaliser.get_random_question(key)
            else:
                key = random.sample(PREDICATE_SET.difference(follow_ups), 1)[0]
                follow_ups.add(key)
                ctx["persqa:predicate"] = key
                output = verbaliser.get_random_followup_question(key)
                logger.error(f"FOLLOW_UP: Intent = {key}")
            ctx["rawio:out"] = output
            ctx["persqa:subject"] = interloc_path

        @state(cond=s("nlp:triples:changed"),
               read=("nlp:triples", "nlp:yesno", "persqa:subject"))
        def fup_react(ctx: ContextWrapper):
            logger.error("I am in FU")

        mod.add(small_talk)
        ctx.add_state(small_talk)
        mod.add(fup_react)
        ctx.add_state(fup_react)


    @state(cond=s("nlp:triples:changed"),
           write="persqa:answer",
           read=("persqa:predicate", "nlp:triples", "nlp:tokens", "nlp:yesno"))
    def inference(ctx: ContextWrapper):
        """
        recognizes name in sentences like:
         - i am jj
         - my name toseban
         - dino
        """
        triple = ctx["nlp:triples"][0]
        if ctx["persqa:predicate"] == "NAME" or ctx["persqa:predicate"] in PREDICATE_SET:
            ctx["persqa:answer"] = triple.get_object()
            if len(ctx["nlp:tokens"]) == 1:
                ctx["persqa:answer"] = ctx["nlp:tokens"][0]
            elif len(ctx["nlp:tokens"]) == 2:
                ctx["persqa:answer"] = "%s %s" % (ctx["nlp:tokens"][0], ctx["nlp:tokens"][1])
            if ctx["nlp:yesno"] == "no":
                pass
        # TODO check if interloc only says no


    @state(cond=s("persqa:answer:changed"),
           write=("rawio:out", "interloc:all", "persqa:predicate"),
           read=("persqa:predicate", "persqa:subject", "persqa:answer", "interloc:all"))
    def react(ctx: ContextWrapper):
        """
        retrieves memory node with the name or creates a new one
        outputs a polite response
        """
        onto: Ontology = ravestate_ontology.get_ontology()
        sess: Session = ravestate_ontology.get_session()
        interloc_answer = str(ctx["persqa:answer"])
        pers_info = ctx["persqa:predicate"]
        # subject_node = Node(node=ctx[ctx["persqa:subject"]])
        subject_node: Node = ctx[ctx["persqa:subject"]]
        if pers_info == "NAME":
            subject_node.set_name(interloc_answer)
            subject_node, output = retrieve_node(subject_node, pers_info, interloc_answer)
            ctx["rawio:out"] = output
        elif pers_info in PREDICATE_SET:
            if pers_info == "FROM" or pers_info == "LIVE_IN":
                relationship_node = Node(metatype=onto.get_type("Location"))  #
                # TODO City, Country -> NLP NER also only recognizes locations...
            elif pers_info == "HAS_HOBBY":
                relationship_node = Node(metatype=onto.get_type("Hobby"))
            elif pers_info == "FRIEND_OF":
                relationship_node = Node(metatype=onto.get_type("Person"))  # TODO Robot
            elif pers_info == "STUDY_AT":
                relationship_node = Node(metatype=onto.get_type("University"))
            elif pers_info == "MEMBER_OF":
                relationship_node = Node(metatype=onto.get_type("Organization"))
            elif pers_info == "WORK_FOR":
                relationship_node = Node(metatype=onto.get_type("Company"))
            elif pers_info == "OCCUPIED_AS":
                relationship_node = Node(metatype=onto.get_type("Occupation"))  # TODO Job
            else:
                relationship_node = Node()
            relationship_node.set_name(interloc_answer)
            relationship_node, output = retrieve_node(relationship_node, pers_info, interloc_answer)
            ctx["rawio:out"] = output
            if relationship_node is not None:
                subject_node.add_relationships({pers_info: {relationship_node.get_id()}})
                sess.update(subject_node)
        ctx["persqa:predicate"] = None
        create_small_talk_state(ctx=ctx, interloc_path=ctx["persqa:subject"])


    def retrieve_node(node: Node, intent: str, interloc_answer: str):
        # TODO follow uo logic is not right yet; works only for name
        sess: Session = ravestate_ontology.get_session()
        node_list = sess.retrieve(node)
        if not node_list:
            node = sess.create(node)
            output = verbaliser.get_random_successful_answer(intent) % interloc_answer
        elif len(node_list) == 1:
            node = node_list[0]
            output = verbaliser.get_random_followup_answer(intent) % interloc_answer
        else:
            logger.error("Found more than one node with that name!")
            node = None
            output = verbaliser.get_random_failure_answer(intent)
        if node is not None:
            logger.info(f"Interlocutor: Answer = {answer}; Node ID = {node.get_id()} ")
        return node, output

