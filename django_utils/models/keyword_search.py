from functools import reduce
from operator import ior
from django.db.models import Q, Max

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
)
from django.db import models
from ddtrace import tracer

from typing import List


class KeywordSearchQuerySet(models.QuerySet):
    """
    This is an abstract class that implements generic keyword-search for any django
    model. To implement keyword-search, extend this class and overwrite the appropriate
    class variables for the search type you're using.
    Most of the fields are defined as a list of strings; the strings should be django
    fields, including relational fields. (eg. related_model__location_id)
    """

    ### General Fields ###
    # keyword search will call prefetch_relations on this list. This frontloads the db
    #   query for ralated data you know will be used, avoiding extra round-trips.
    PREFETCH_RELATIONS: List[str] = []

    ### Full Text Search ###
    # These fields will be searched when using full text search
    FULLTEXT_SEARCH_FIELDS: List[str] = []

    ### Trigram Search ###
    # Trigram search won't search if the search query is shorter than this many chars
    #   Trigram search can be very noisey with shorter search queries.
    MINIMUM_TRIGRAM_LENGTH: int = 3

    # Any results with at least this percentage of similarity to the search query in
    #   ANY of the searched fields will be returned.
    TRIGRAM_SIMILARITY_THRESHOLD: float = 0.1

    # List of django fields to perform a trigram search on.
    TRIGRAM_SEARCH_FIELDS: List[str] = []

    # OPTIONAL; fields to order a trigram search by; if not defined,
    #   TRIGRAM_SEARCH_FIELDS will be used for ordering instead.
    TRIGRAM_ORDER_BY: List[str] = []

    @tracer.wrap(name="keyword search")
    def keyword_search(self, keywords: str) -> "KeywordSearchQuerySet":
        """
        Perform a keyword search of the queryset using the `combination_search` method.

        This implementation uses PostgreSQL-specific features, therefore it will only
        work with models stored in PostgreSQL.
        """
        span = tracer.current_span()
        span.set_tags(
            {
                "search-type": "postgres combination trigram and full-text search",
                "model": self.model,
                "search phrase": keywords,
            }
        )

        if not (self.FULLTEXT_SEARCH_FIELDS or self.TRIGRAM_SEARCH_FIELDS):
            return self
        return self.combination_search(keywords)

    def trigram_search(self, search_query: str) -> "KeywordSearchQuerySet":
        """
        Executes a trigram search across multiple fields. The fields to search are
        configured in the class variable TRIGRAM_SEARCH_FIELDS in extending classes. Any
        records with at least 1 field which has a trigram-similarity above
        TRIGRAM_SIMILARITY_THRESHOLD will be returned in the result.

        This implementation uses PostgreSQL-specific features, therefore it will only
        work with models stored in PostgreSQL.
        """
        # TODO -- (PD-7045) We are currently iterating on search. I don't want to remove this code
        #       until I'm confident that we will not use it in the near future.
        if not search_query:
            return self.model.objects.none()
        query = None
        annotations = {}
        for field_name in self.TRIGRAM_SEARCH_FIELDS:
            similarity = field_name + "_similarity"
            annotations[similarity] = Max(TrigramSimilarity(field_name, search_query))
            new_query = Q(**{similarity + "__gt": self.TRIGRAM_SIMILARITY_THRESHOLD})
            if query is None:
                query = new_query
            else:
                query |= new_query
        queryset = self.annotate(**annotations).filter(query)
        order_by_values = self._order_by_list()
        queryset = queryset.order_by(*order_by_values)
        return queryset

    @classmethod
    def _order_by_list(cls):
        """
        returns the list of order-by fields for trigram-similarity, automatically
        generating order-by fields based on a list of field names. By default, will use
        the TRIGRAM_SEARCH_FIELDS values, but these can be explicitly overwritten by
        defining TRIGRAM_ORDER_BY on a subclass.
        """
        # defaults to TRIGRAM_SEARCH_FIELDS, which is required, but can be overridden by
        #   TRIGRAM_ORDER_BY

        ls = cls.TRIGRAM_ORDER_BY or cls.TRIGRAM_SEARCH_FIELDS
        # appends "_similarity" to field names.
        return list(map(lambda field_name: "-" + field_name + "_similarity", ls))

    def fulltext_search(self, keywords: str) -> "KeywordSearchQuerySet":
        """
        Given a string, split it into words, perform a PostgreSQL full text search on
        the QuerySet, and return a QuerySet ordered by search rank.

        Uses FULLTEXT_SEARCH_FIELDS to configure which fields are searched on the target
        model.

        This implementation uses PostgreSQL-specific features, therefore it will only
        work with models stored in PostgreSQL.

        :param keywords: String of whitespace separated words.
        :return: django QuerySet
        """
        # TODO -- (PD-7045) We are currently iterating on search. I don't want to remove this code
        #       until I'm confident that we will not use it in the near future.
        search_query = self._get_search_query(keywords)
        if not search_query:
            return self.model.objects.none()

        search_vector = SearchVector(*self.FULLTEXT_SEARCH_FIELDS)
        search_rank = SearchRank(search_vector, search_query)
        search_result = (
            self.annotate(rank=search_rank, search=search_vector)
            .filter(search=search_query)
            .prefetch_related(*self.PREFETCH_RELATIONS)
            .order_by("-rank")
        )
        return search_result

    def combination_search(self, search_str: str) -> "KeywordSearchQuerySet":
        """
        Perform a search using both PostgreSQL trigram similarity search, and PostgreSQL
        full text search, combining their results to harness the useful aspects of both
        techniques.

        This implementation uses PostgreSQL-specific features, therefore it will only
        work with models stored in PostgreSQL.
        """
        if not search_str or len(search_str) < self.MINIMUM_TRIGRAM_LENGTH:
            return self.none()

        ### FULLTEXT SEARCH CODE ###
        fulltext_query = self._get_search_query(search_str)
        if not fulltext_query:
            return self.none()

        fulltext_vector = SearchVector(*self.FULLTEXT_SEARCH_FIELDS)
        fulltext_rank = SearchRank(fulltext_vector, fulltext_query)

        ### TRIGRAM SEARCH CODE ###
        trigram_query = None
        tg_annotations = {}
        for field_name in self.TRIGRAM_SEARCH_FIELDS:
            similarity = field_name + "_similarity"
            tg_annotations[similarity] = Max(TrigramSimilarity(field_name, search_str))
            new_query = Q(**{similarity + "__gt": self.TRIGRAM_SIMILARITY_THRESHOLD})
            if trigram_query is None:
                trigram_query = new_query
            else:
                trigram_query |= new_query
        trigram_order_by_values = self._order_by_list()

        ### Build Combination Queryset ###
        queryset = self.annotate(
            fulltext_rank=fulltext_rank,
            fulltext_search=fulltext_vector,
            **tg_annotations,
        )

        combination_query = trigram_query | Q(fulltext_search=fulltext_query)
        queryset = queryset.filter(combination_query)
        queryset = queryset.prefetch_related(*self.PREFETCH_RELATIONS)
        return queryset.order_by(*trigram_order_by_values, "-fulltext_rank")

    def _get_search_ranking(self):
        """
        Debugging method; assumes "keyword_search" has been run, and returns django
        `values` queryset containing the search rankings for that search.
        """
        tg_rankings = [field.replace("-", "") for field in self._order_by_list()]
        return self.values(*tg_rankings, "fulltext_rank")

    @classmethod
    def _get_search_query(cls, keywords: str):
        """
        breaks a string into keywords and returns a postgres SearchQuery object, used
        for a Full Text search. If emptystring is passed, Nonetype is returned.
        :param keywords: a string
        :return:
        """
        if not keywords:
            return

        queries = [SearchQuery(word) for word in keywords.split(" ") if word]
        search_query = reduce(ior, queries)
        return search_query
