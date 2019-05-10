from ravestate.module import Module
from ravestate.property import Property
from ravestate.wrappers import ContextWrapper
from ravestate.state import state, Emit, Delete, Resign
from ravestate.constraint import s, Signal
from ravestate_verbaliser import verbaliser
import ravestate_ontology

from os.path import realpath, dirname, join
from typing import Dict, Set
from collections import defaultdict
import random

from scientio.ontology.ontology import Ontology
from scientio.session import Session
from scientio.ontology.node import Node
from reggol import get_logger
logger = get_logger(__name__)

from ravestate_idle import bored
from ravestate_rawio import input as raw_in, output as raw_out
from ravestate_nlp import triples, yesno, tokens
from ravestate_interloc import all as interloc_all

verbaliser.add_folder(join(dirname(realpath(__file__)), "persqa_phrases"))

PREDICATE_SET = {"FROM", "HAS_HOBBY", "LIVE_IN", "FRIEND_OF", "STUDY_AT", "MEMBER_OF", "WORK_FOR", "OCCUPIED_AS"}
ONTOLOGY_TYPE_FOR_PRED = defaultdict(str, {
    "FROM": "Location",
    "LIVE_IN": "Location",
    "HAS_HOBBY": "Hobby",
    "FRIEND_OF": "Person",  # TODO Robot
    "STUDY_AT": "University",
    "MEMBER_OF": "Organization",
    "WORK_FOR": "Company",
    "OCCUPIED_AS": "Occupation"
})
# TODO "movies", "OTHER"
# TODO "sex", "birth date", "full name"
# TODO "EQUALS"


with Module(name="persqa") as mod:

    # This is a nice demo of using properties as synchronization
    #  primitives. The problem: inference must only run for inputs
    #  that did not trigger new_interloc. Therefore, new_interloc and inference
    #  are mutually exclusive. This is enfored by having both of them
    #  consume the inference_mutex property.
    inference_mutex = Property(name="inference_mutex")

    subject = Property(
        name="subject",
        default_value="",
        always_signal_changed=True,
        allow_pop=False,
        allow_push=False,
        is_flag_property=True)

    predicate = Property(
        name="predicate",
        default_value="",
        always_signal_changed=True,
        allow_pop=False,
        allow_push=False,
        is_flag_property=True)

    answer = Property(
        name="answer",
        default_value="",
        always_signal_changed=True,
        allow_pop=False,
        allow_push=False,
        is_flag_property=True)

    follow_up_prop = Property(
        name="follow_up",
        default_value="",
        always_signal_changed=True,
        allow_pop=False,
        allow_push=False)

    follow_up_signal = Signal(name="follow-up")

    def find_empty_relationship(dictonary: Dict):
        for key in dictonary:
            if not dictonary[key] and key in PREDICATE_SET:
                return key
        return None

    def retrieve_or_create_node(node: Node):
        sess: Session = ravestate_ontology.get_session()
        node_list = sess.retrieve(node)
        if not node_list:
            node = sess.create(node)
        elif len(node_list) > 0:
            node = node_list[0]
        return node

    def create_small_talk_states(ctx: ContextWrapper, interloc_path: str):

        used_follow_up_preds = set()

        @state(cond=bored,
               write=(raw_out, predicate, subject),
               read=(interloc_path, predicate),
               weight=1.2,
               cooldown=40.,
               emit_detached=True,
               signal=follow_up_signal)
        def small_talk(ctx: ContextWrapper):
            sess: Session = ravestate_ontology.get_session()
            interloc: Node = ctx[interloc_path]
            if interloc.get_id() < 0:  # ask for name, if the interlocutor is not (yet) a persistent instance
                pred = "NAME"
            else:
                pred = find_empty_relationship(interloc.get_relationships())
            ctx[subject] = interloc_path
            if not ctx[predicate]:
                if pred:
                    logger.info(f"Personal question: intent={pred}")
                    ctx[predicate] = pred
                    ctx[raw_out] = verbaliser.get_random_question(pred)
                else:
                    unused_fup_preds = PREDICATE_SET.difference(used_follow_up_preds)
                    if not unused_fup_preds:
                        logger.info(f"Ran out of smalltalk predicates for {interloc_path}, committing suicide...")
                        return Delete(resign=True)
                    pred = random.sample(PREDICATE_SET.difference(used_follow_up_preds), 1)
                    pred = pred[0]
                    used_follow_up_preds.add(pred)
                    ctx[predicate] = pred
                    relationship_ids: Set[int] = interloc.get_relationships(pred)
                    if len(relationship_ids) > 0:  # Just to be safe ...
                        object_node_list = sess.retrieve(node_id=list(relationship_ids)[0])
                        if len(object_node_list) > 0:
                            ctx[raw_out] = verbaliser.get_random_followup_question(pred).format(
                                name=interloc.get_name(),
                                obj=object_node_list[0].get_name())
                            logger.info(f"Follow-up: intent={pred}")
                            return Emit()
                    return Resign()
            else:
                # While the predicate is set, repeat the question. Once the predicate is answered,
                #  it will be set to None, such that a new predicate is entered.
                ctx[raw_out] = verbaliser.get_random_question(ctx[predicate])

        @state(cond=follow_up_signal.max_age(-1.) & triples.changed_signal(),
               write=(raw_out, predicate, inference_mutex),
               read=(interloc_path, predicate, yesno))
        def fup_react(ctx: ContextWrapper):
            sess: Session = ravestate_ontology.get_session()
            subject_node: Node = ctx[interloc_path]
            pred = ctx[predicate]
            object_node_list = []
            relationship_ids: Set[int] = subject_node.get_relationships(pred)
            if len(relationship_ids) > 0:
                object_node_list = sess.retrieve(node_id=list(relationship_ids)[0])
            if len(object_node_list) > 0:
                ctx[raw_out] = verbaliser.get_random_followup_answer(pred).format(
                    name=subject_node.get_name(),
                    obj=object_node_list[0].get_name())
            else:
                ctx[raw_out] = "Oh, I see!"
            ctx[predicate] = None

        ctx.add_state(small_talk)
        ctx.add_state(fup_react)

    @state(cond=raw_in.changed_signal() & interloc_all.pushed_signal(),
           write=inference_mutex,
           read=interloc_all,
           emit_detached=True)
    def new_interloc(ctx: ContextWrapper):
        """
        reacts to interloc:pushed and creates persqa:ask_name state
        """
        interloc_path = ctx[interloc_all.pushed_signal()]
        create_small_talk_states(ctx=ctx, interloc_path=interloc_path)

    @state(cond=raw_in.changed_signal() & interloc_all.popped_signal(),
           write=(inference_mutex, predicate, subject))
    def removed_interloc(ctx: ContextWrapper):
        """
        reacts to interloc:popped and makes sure that
        """
        ctx[subject] = None
        ctx[predicate] = None

    @state(cond=triples.changed_signal(),
           write=(answer, inference_mutex),
           read=(predicate, triples, tokens, yesno))
    def inference(ctx: ContextWrapper):
        """
        recognizes name in sentences like:
         - i am jj
         - my name toseban
         - dino
        """
        triple = ctx[triples][0]
        if triple.is_question():
            return Resign()
        pred = ctx[predicate]
        answer_str = None
        if pred == "NAME" or pred in PREDICATE_SET:
            # TODO City, Country -> NLP NER also only recognizes locations...
            if triple.has_object():
                answer_str = triple.get_object().text
            elif len(ctx[tokens]) == 1:
                answer_str = ctx[tokens][0]
            elif len(ctx[tokens]) == 2:
                answer_str = "%s %s" % (ctx[tokens][0], ctx[tokens][1])
        if answer_str:
            logger.debug(f"Inference: extracted answer '{answer_str}' for predicate {pred}")
            ctx[answer] = answer_str

    @state(cond=answer.changed_signal(),
           write=(raw_out, predicate),
           read=(predicate, subject, answer, interloc_all))
    def react(ctx: ContextWrapper):
        """
        Retrieves memory node with the name, or creates a new one
        outputs a polite response.
        """
        onto: Ontology = ravestate_ontology.get_ontology()
        sess: Session = ravestate_ontology.get_session()
        inferred_answer = ctx[answer]
        pred = ctx[predicate]
        subject_path: str = ctx[subject]
        if not subject_path:
            return Resign()
        subject_node: Node = ctx[subject_path]
        assert inferred_answer

        if pred == "NAME":
            # If name was asked, it must be because the node is not yet persistent
            assert subject_node.get_id() < 0
            subject_node.set_name(inferred_answer)
            persistent_subject_node = retrieve_or_create_node(subject_node)
            # TODO: Workaround - see #83 - if this state would write to interloc:all,
            #  it would promise an interloc:all:pushed signal. This would be
            #  picked up by persqa:new_interloc.
            subject_node.set_node(persistent_subject_node)
            sess.update(subject_node)
        elif pred in PREDICATE_SET:
            relationship_type = onto.get_type(ONTOLOGY_TYPE_FOR_PRED[pred])
            relationship_node = Node(metatype=relationship_type)
            relationship_node.set_name(inferred_answer)
            relationship_node = retrieve_or_create_node(relationship_node)
            if relationship_node is not None:
                subject_node.add_relationships({pred: {relationship_node.get_id()}})
                sess.update(subject_node)

        ctx[raw_out] = verbaliser.get_random_successful_answer(pred).format(
            name=subject_node.get_name(),
            obj=inferred_answer)
        ctx[predicate] = None


