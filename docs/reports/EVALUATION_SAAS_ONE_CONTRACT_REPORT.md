# Full Contract-Agent Evaluation Report

Generated: 2026-05-23T02:49:56.231310
Layers: agents, chat, deepeval, tools
Total cases: 29

## Executive Summary

- Mean score: 0.782
- Median score: 0.798
- Pass rate: 48.3%
- Duration: 3955.1s

## Category Scores

| Category | Cases | Mean Score |
|---|---:|---:|
| clause_analysis | 10 | 0.592 |
| compliance | 1 | 1.000 |
| compound_orchestration | 1 | 0.667 |
| conversational | 3 | 0.971 |
| general_query | 3 | 0.966 |
| key_dates | 1 | 0.987 |
| obligation_tracking | 2 | 0.630 |
| qa_answer | 1 | 0.963 |
| qa_generation | 1 | 1.000 |
| redflags | 1 | 0.930 |
| risk_detection | 4 | 0.836 |
| summary | 1 | 0.798 |

## Layer Scores

| Layer | Cases | Mean Score |
|---|---:|---:|
| agents | 29 | 0.703 |
| chat | 29 | 0.642 |
| tools | 29 | 1.000 |

## Failure Types

| Failure | Count |
|---|---:|
| `incomplete_answer` | 16 |
| `missing_citation` | 11 |
| `retrieval_miss` | 11 |
| `timeout` | 11 |
| `agent_retrieval_miss` | 9 |
| `intent_mismatch` | 5 |
| `agent_incomplete_answer` | 4 |
| `false_negative` | 1 |

## Case Results

| Case | Category | Score | Failures |
|---|---|---:|---|
| `case_0000_saas_agreement_summary` | summary | 0.798 | `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0001_saas_agreement_clause_ARTICLE_1_-_DEFINITIONS

###_1.1_"Agreement"_means_this_SaaS_Agreement_including_all_Exhibits_and_Schedules.

###_1.2_"Confidential_Information"_means_all_non-public_information_disclosed_by_one_party_to_the_other,_whether_orally_or_in_writing,_that_is_designated_as_confidential_or_that_reasonably_should_be_understood_to_be_confidential.

###_1.3_"Documentation"_means_Provider's_user_guides,_documentation,_and_specifications_for_the_Service.

###_1.4_"Service"_means_the_software-as-a-service_platform_known_as_"CloudServe_Enterprise"_as_described_in_Exhibit_A.

###_1.5_"Subscription_Term"_means_the_period_during_which_Customer_is_authorized_to_access_and_use_the_Service,_as_specified_in_Exhibit_B.

##_ARTICLE_2_-_SUBSCRIPTION_AND_ACCESS

###_2.1_Subscription_Grant
Subject_to_the_terms_of_this_Agreement_and_payment_of_applicable_fees,_Provider_grants_Customer_a_non-exclusive,_non-transferable_right_to_access_and_use_the_Service_during_the_Subscription_Term.

###_2.2_User_Limits
Customer's_access_is_limited_to_the_number_of_Authorized_Users_specified_in_Exhibit_B._Customer_may_increase_the_number_of_Authorized_Users_upon_written_notice_and_payment_of_applicable_fees.

###_2.3_Restrictions
Customer_shall_not` | clause_analysis | 0.519 | `agents:timeout`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0002_saas_agreement_clause_ARTICLE_3_-_SERVICE_LEVEL_AGREEMENT

###_3.1_Uptime_Commitment
Provider_shall_maintain_uptime_availability_of_ninety-nine_percent_(99.0%)_during_normal_business_hours_and_ninety-nine_percent_(99.0%)_overall_in_any_given_calendar_month.

###_3.2_Downtime_Exclusions
Downtime_does_not_include` | clause_analysis | 0.519 | `agents:timeout`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0003_saas_agreement_clause_ARTICLE_4_-_FEES_AND_PAYMENT

###_4.1_Subscription_Fees
Customer_shall_pay_the_subscription_fees_specified_in_Exhibit_B._All_fees_are_non-refundable_and_payable_in_United_States_Dollars.

###_4.2_Payment_Terms
Fees_are_payable_annually_in_advance._Late_payments_shall_accrue_interest_at_the_rate_of_1.5%_per_month_or_the_maximum_rate_permitted_by_law,_whichever_is_lower.

###_4.3_Price_Increases
Provider_may_increase_subscription_fees_upon_renewal_by_providing_ninety_(90)_days_prior_written_notice._Price_increases_shall_not_exceed_fifteen_percent_(15%)_of_the_prior_year's_fees.

###_4.4_Taxes
Fees_are_exclusive_of_taxes._Customer_is_responsible_for_all_sales,_use,_and_value-added_taxes_associated_with_the_Service.

##_ARTICLE_5_-_DATA_SECURITY_AND_PRIVACY

###_5.1_Security_Measures
Provider_shall_implement_and_maintain_reasonable_administrative,_physical,_and_technical_safeguards_to_protect_Customer_Data,_including_encryption_in_transit_and_at_rest.

###_5.2_Data_Breach_Notification
Provider_shall_notify_Customer_within_seventy-two_(72)_hours_of_becoming_aware_of_any_unauthorized_access_to_Customer_Data.

###_5.3_Compliance
Provider_shall_comply_with_applicable_data_protection_laws_including_GDPR_for_EU_personal_data_and_CCPA_for_California_personal_information.

##_ARTICLE_6_-_INTELLECTUAL_PROPERTY

###_6.1_Provider_IP
Provider_retains_all_rights,_title,_and_interest_in_and_to_the_Service,_Documentation,_and_any_modifications_or_improvements_thereto.

###_6.2_Customer_Data
Customer_retains_all_rights,_title,_and_interest_in_and_to_Customer_Data._Customer_grants_Provider_a_limited_license_to_host,_copy,_and_transmit_Customer_Data_solely_for_providing_the_Service.

###_6.3_Feedback
Customer_grants_Provider_a_perpetual,_irrevocable,_royalty-free_license_to_use_any_feedback_provided_about_the_Service.

##_ARTICLE_7_-_CONFIDENTIALITY

###_7.1_Obligations
Each_party_shall` | clause_analysis | 0.333 | `agents:timeout`, `chat:timeout` |
| `case_0004_saas_agreement_clause_ARTICLE_8_-_WARRANTIES_AND_DISCLAIMERS

###_8.1_Mutual_Warranty
Each_party_represents_and_warrants_that_it_has_the_authority_to_enter_into_this_Agreement.

###_8.2_Service_Warranty
Provider_warrants_that_the_Service_will_perform_substantially_in_accordance_with_the_Documentation_under_normal_use.

###_8.3_Disclaimer
EXCEPT_AS_EXPRESSLY_STATED,_THE_SERVICE_IS_PROVIDED_"AS_IS"_WITHOUT_WARRANTY_OF_ANY_KIND,_EXPRESS_OR_IMPLIED,_INCLUDING_BUT_NOT_LIMITED_TO_WARRANTIES_OF_MERCHANTABILITY,_FITNESS_FOR_A_PARTICULAR_PURPOSE,_OR_NON-INFRINGEMENT.

##_ARTICLE_9_-_LIMITATION_OF_LIABILITY

###_9.1_Consequential_Damages_Waiver
NEITHER_PARTY_SHALL_BE_LIABLE_FOR_INDIRECT,_INCIDENTAL,_SPECIAL,_CONSEQUENTIAL,_OR_PUNITIVE_DAMAGES,_OR_LOST_PROFITS,_REGARDLESS_OF_THE_CAUSE_OF_ACTION_AND_EVEN_IF_ADVISED_OF_THE_POSSIBILITY_OF_SUCH_DAMAGES.

###_9.2_Liability_Cap
EXCEPT_FOR_BREACHES_OF_SECTION_2.3_(RESTRICTIONS),_SECTION_7_(CONFIDENTIALITY),_OR_CUSTOMER'S_PAYMENT_OBLIGATIONS,_EACH_PARTY'S_TOTAL_AGGREGATE_LIABILITY_SHALL_NOT_EXCEED_THE_FEES_PAID_OR_PAYABLE_BY_CUSTOMER_IN_THE_TWELVE_(12)_MONTHS_PRECEDING_THE_CLAIM.

###_9.3_Exceptions
The_liability_cap_shall_not_apply_to` | clause_analysis | 0.333 | `agents:timeout`, `chat:timeout` |
| `case_0005_saas_agreement_clause_ARTICLE_10_-_TERM_AND_TERMINATION

###_10.1_Initial_Term
This_Agreement_shall_commence_on_the_Effective_Date_and_continue_for_the_Initial_Term_specified_in_Exhibit_B.

###_10.2_Renewal
This_Agreement_shall_automatically_renew_for_successive_one_(1)_year_periods_unless_either_party_provides_written_notice_of_non-renewal_at_least_ninety_(90)_days_prior_to_the_end_of_the_then-current_term.

###_10.3_Termination_for_Cause
Either_party_may_terminate_this_Agreement_for_material_breach_if_the_breaching_party_fails_to_cure_such_breach_within_thirty_(30)_days_after_written_notice.

###_10.4_Insolvency
Either_party_may_terminate_immediately_upon_written_notice_if_the_other_party_becomes_insolvent,_files_for_bankruptcy,_or_ceases_business_operations.

###_10.5_Effect_of_Termination
Upon_termination` | clause_analysis | 0.333 | `agents:timeout`, `chat:timeout` |
| `case_0006_saas_agreement_obligation_1` | obligation_tracking | 0.631 | `agents:timeout`, `chat:incomplete_answer` |
| `case_0007_saas_agreement_risk_1` | risk_detection | 0.970 | None |
| `case_0008_saas_agreement_parties` | general_query | 0.958 | `chat:incomplete_answer`, `chat:intent_mismatch` |
| `case_0009_saas_agreement_key_dates` | key_dates | 0.987 | `chat:intent_mismatch` |
| `case_0010_saas_agreement_compliance_1` | compliance | 1.000 | None |
| `case_0011_saas_agreement_qa_generate` | qa_generation | 1.000 | None |
| `case_0012_saas_agreement_conversational` | conversational | 0.971 | `chat:incomplete_answer` |
| `case_0013_saas_agreement_clause_q_ARTICLE_1_-_DEFINITIONS

###_1.1_"Agreement"_means_this_SaaS_Agreement_including_all_Exhibits_and_Schedules.

###_1.2_"Confidential_Information"_means_all_non-public_information_disclosed_by_one_party_to_the_other,_whether_orally_or_in_writing,_that_is_designated_as_confidential_or_that_reasonably_should_be_understood_to_be_confidential.

###_1.3_"Documentation"_means_Provider's_user_guides,_documentation,_and_specifications_for_the_Service.

###_1.4_"Service"_means_the_software-as-a-service_platform_known_as_"CloudServe_Enterprise"_as_described_in_Exhibit_A.

###_1.5_"Subscription_Term"_means_the_period_during_which_Customer_is_authorized_to_access_and_use_the_Service,_as_specified_in_Exhibit_B.

##_ARTICLE_2_-_SUBSCRIPTION_AND_ACCESS

###_2.1_Subscription_Grant
Subject_to_the_terms_of_this_Agreement_and_payment_of_applicable_fees,_Provider_grants_Customer_a_non-exclusive,_non-transferable_right_to_access_and_use_the_Service_during_the_Subscription_Term.

###_2.2_User_Limits
Customer's_access_is_limited_to_the_number_of_Authorized_Users_specified_in_Exhibit_B._Customer_may_increase_the_number_of_Authorized_Users_upon_written_notice_and_payment_of_applicable_fees.

###_2.3_Restrictions
Customer_shall_not` | clause_analysis | 0.769 | `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0014_saas_agreement_clause_q_ARTICLE_3_-_SERVICE_LEVEL_AGREEMENT

###_3.1_Uptime_Commitment
Provider_shall_maintain_uptime_availability_of_ninety-nine_percent_(99.0%)_during_normal_business_hours_and_ninety-nine_percent_(99.0%)_overall_in_any_given_calendar_month.

###_3.2_Downtime_Exclusions
Downtime_does_not_include` | clause_analysis | 0.785 | `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0015_saas_agreement_clause_q_ARTICLE_4_-_FEES_AND_PAYMENT

###_4.1_Subscription_Fees
Customer_shall_pay_the_subscription_fees_specified_in_Exhibit_B._All_fees_are_non-refundable_and_payable_in_United_States_Dollars.

###_4.2_Payment_Terms
Fees_are_payable_annually_in_advance._Late_payments_shall_accrue_interest_at_the_rate_of_1.5%_per_month_or_the_maximum_rate_permitted_by_law,_whichever_is_lower.

###_4.3_Price_Increases
Provider_may_increase_subscription_fees_upon_renewal_by_providing_ninety_(90)_days_prior_written_notice._Price_increases_shall_not_exceed_fifteen_percent_(15%)_of_the_prior_year's_fees.

###_4.4_Taxes
Fees_are_exclusive_of_taxes._Customer_is_responsible_for_all_sales,_use,_and_value-added_taxes_associated_with_the_Service.

##_ARTICLE_5_-_DATA_SECURITY_AND_PRIVACY

###_5.1_Security_Measures
Provider_shall_implement_and_maintain_reasonable_administrative,_physical,_and_technical_safeguards_to_protect_Customer_Data,_including_encryption_in_transit_and_at_rest.

###_5.2_Data_Breach_Notification
Provider_shall_notify_Customer_within_seventy-two_(72)_hours_of_becoming_aware_of_any_unauthorized_access_to_Customer_Data.

###_5.3_Compliance
Provider_shall_comply_with_applicable_data_protection_laws_including_GDPR_for_EU_personal_data_and_CCPA_for_California_personal_information.

##_ARTICLE_6_-_INTELLECTUAL_PROPERTY

###_6.1_Provider_IP
Provider_retains_all_rights,_title,_and_interest_in_and_to_the_Service,_Documentation,_and_any_modifications_or_improvements_thereto.

###_6.2_Customer_Data
Customer_retains_all_rights,_title,_and_interest_in_and_to_Customer_Data._Customer_grants_Provider_a_limited_license_to_host,_copy,_and_transmit_Customer_Data_solely_for_providing_the_Service.

###_6.3_Feedback
Customer_grants_Provider_a_perpetual,_irrevocable,_royalty-free_license_to_use_any_feedback_provided_about_the_Service.

##_ARTICLE_7_-_CONFIDENTIALITY

###_7.1_Obligations
Each_party_shall` | clause_analysis | 0.769 | `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0016_saas_agreement_clause_q_ARTICLE_8_-_WARRANTIES_AND_DISCLAIMERS

###_8.1_Mutual_Warranty
Each_party_represents_and_warrants_that_it_has_the_authority_to_enter_into_this_Agreement.

###_8.2_Service_Warranty
Provider_warrants_that_the_Service_will_perform_substantially_in_accordance_with_the_Documentation_under_normal_use.

###_8.3_Disclaimer
EXCEPT_AS_EXPRESSLY_STATED,_THE_SERVICE_IS_PROVIDED_"AS_IS"_WITHOUT_WARRANTY_OF_ANY_KIND,_EXPRESS_OR_IMPLIED,_INCLUDING_BUT_NOT_LIMITED_TO_WARRANTIES_OF_MERCHANTABILITY,_FITNESS_FOR_A_PARTICULAR_PURPOSE,_OR_NON-INFRINGEMENT.

##_ARTICLE_9_-_LIMITATION_OF_LIABILITY

###_9.1_Consequential_Damages_Waiver
NEITHER_PARTY_SHALL_BE_LIABLE_FOR_INDIRECT,_INCIDENTAL,_SPECIAL,_CONSEQUENTIAL,_OR_PUNITIVE_DAMAGES,_OR_LOST_PROFITS,_REGARDLESS_OF_THE_CAUSE_OF_ACTION_AND_EVEN_IF_ADVISED_OF_THE_POSSIBILITY_OF_SUCH_DAMAGES.

###_9.2_Liability_Cap
EXCEPT_FOR_BREACHES_OF_SECTION_2.3_(RESTRICTIONS),_SECTION_7_(CONFIDENTIALITY),_OR_CUSTOMER'S_PAYMENT_OBLIGATIONS,_EACH_PARTY'S_TOTAL_AGGREGATE_LIABILITY_SHALL_NOT_EXCEED_THE_FEES_PAID_OR_PAYABLE_BY_CUSTOMER_IN_THE_TWELVE_(12)_MONTHS_PRECEDING_THE_CLAIM.

###_9.3_Exceptions
The_liability_cap_shall_not_apply_to` | clause_analysis | 0.792 | `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0017_saas_agreement_clause_q_ARTICLE_10_-_TERM_AND_TERMINATION

###_10.1_Initial_Term
This_Agreement_shall_commence_on_the_Effective_Date_and_continue_for_the_Initial_Term_specified_in_Exhibit_B.

###_10.2_Renewal
This_Agreement_shall_automatically_renew_for_successive_one_(1)_year_periods_unless_either_party_provides_written_notice_of_non-renewal_at_least_ninety_(90)_days_prior_to_the_end_of_the_then-current_term.

###_10.3_Termination_for_Cause
Either_party_may_terminate_this_Agreement_for_material_breach_if_the_breaching_party_fails_to_cure_such_breach_within_thirty_(30)_days_after_written_notice.

###_10.4_Insolvency
Either_party_may_terminate_immediately_upon_written_notice_if_the_other_party_becomes_insolvent,_files_for_bankruptcy,_or_ceases_business_operations.

###_10.5_Effect_of_Termination
Upon_termination` | clause_analysis | 0.769 | `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0018_saas_agreement_obligation_specific_0` | obligation_tracking | 0.628 | `agents:agent_incomplete_answer`, `chat:timeout` |
| `case_0019_saas_agreement_risk_ARTICLE_1_-_DEFINITIONS

###_1.1_"Agreement"_means_this_SaaS_Agreement_including_all_Exhibits_and_Schedules.

###_1.2_"Confidential_Information"_means_all_non-public_information_disclosed_by_one_party_to_the_other,_whether_orally_or_in_writing,_that_is_designated_as_confidential_or_that_reasonably_should_be_understood_to_be_confidential.

###_1.3_"Documentation"_means_Provider's_user_guides,_documentation,_and_specifications_for_the_Service.

###_1.4_"Service"_means_the_software-as-a-service_platform_known_as_"CloudServe_Enterprise"_as_described_in_Exhibit_A.

###_1.5_"Subscription_Term"_means_the_period_during_which_Customer_is_authorized_to_access_and_use_the_Service,_as_specified_in_Exhibit_B.

##_ARTICLE_2_-_SUBSCRIPTION_AND_ACCESS

###_2.1_Subscription_Grant
Subject_to_the_terms_of_this_Agreement_and_payment_of_applicable_fees,_Provider_grants_Customer_a_non-exclusive,_non-transferable_right_to_access_and_use_the_Service_during_the_Subscription_Term.

###_2.2_User_Limits
Customer's_access_is_limited_to_the_number_of_Authorized_Users_specified_in_Exhibit_B._Customer_may_increase_the_number_of_Authorized_Users_upon_written_notice_and_payment_of_applicable_fees.

###_2.3_Restrictions
Customer_shall_not` | risk_detection | 0.812 | `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0020_saas_agreement_risk_ARTICLE_3_-_SERVICE_LEVEL_AGREEMENT

###_3.1_Uptime_Commitment
Provider_shall_maintain_uptime_availability_of_ninety-nine_percent_(99.0%)_during_normal_business_hours_and_ninety-nine_percent_(99.0%)_overall_in_any_given_calendar_month.

###_3.2_Downtime_Exclusions
Downtime_does_not_include` | risk_detection | 0.733 | `agents:agent_incomplete_answer`, `agents:agent_retrieval_miss`, `chat:incomplete_answer`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0021_saas_agreement_risk_ARTICLE_4_-_FEES_AND_PAYMENT

###_4.1_Subscription_Fees
Customer_shall_pay_the_subscription_fees_specified_in_Exhibit_B._All_fees_are_non-refundable_and_payable_in_United_States_Dollars.

###_4.2_Payment_Terms
Fees_are_payable_annually_in_advance._Late_payments_shall_accrue_interest_at_the_rate_of_1.5%_per_month_or_the_maximum_rate_permitted_by_law,_whichever_is_lower.

###_4.3_Price_Increases
Provider_may_increase_subscription_fees_upon_renewal_by_providing_ninety_(90)_days_prior_written_notice._Price_increases_shall_not_exceed_fifteen_percent_(15%)_of_the_prior_year's_fees.

###_4.4_Taxes
Fees_are_exclusive_of_taxes._Customer_is_responsible_for_all_sales,_use,_and_value-added_taxes_associated_with_the_Service.

##_ARTICLE_5_-_DATA_SECURITY_AND_PRIVACY

###_5.1_Security_Measures
Provider_shall_implement_and_maintain_reasonable_administrative,_physical,_and_technical_safeguards_to_protect_Customer_Data,_including_encryption_in_transit_and_at_rest.

###_5.2_Data_Breach_Notification
Provider_shall_notify_Customer_within_seventy-two_(72)_hours_of_becoming_aware_of_any_unauthorized_access_to_Customer_Data.

###_5.3_Compliance
Provider_shall_comply_with_applicable_data_protection_laws_including_GDPR_for_EU_personal_data_and_CCPA_for_California_personal_information.

##_ARTICLE_6_-_INTELLECTUAL_PROPERTY

###_6.1_Provider_IP
Provider_retains_all_rights,_title,_and_interest_in_and_to_the_Service,_Documentation,_and_any_modifications_or_improvements_thereto.

###_6.2_Customer_Data
Customer_retains_all_rights,_title,_and_interest_in_and_to_Customer_Data._Customer_grants_Provider_a_limited_license_to_host,_copy,_and_transmit_Customer_Data_solely_for_providing_the_Service.

###_6.3_Feedback
Customer_grants_Provider_a_perpetual,_irrevocable,_royalty-free_license_to_use_any_feedback_provided_about_the_Service.

##_ARTICLE_7_-_CONFIDENTIALITY

###_7.1_Obligations
Each_party_shall` | risk_detection | 0.827 | `agents:agent_incomplete_answer`, `agents:agent_retrieval_miss`, `chat:missing_citation`, `chat:retrieval_miss` |
| `case_0022_saas_agreement_general_governing_law` | general_query | 0.958 | `chat:incomplete_answer`, `chat:intent_mismatch` |
| `case_0023_saas_agreement_general_termination` | general_query | 0.981 | `chat:intent_mismatch` |
| `case_0024_saas_agreement_conv_thanks` | conversational | 1.000 | None |
| `case_0025_saas_agreement_conv_capabilities` | conversational | 0.942 | `chat:incomplete_answer` |
| `case_0026_saas_agreement_redflags` | redflags | 0.930 | `agents:agent_incomplete_answer`, `chat:incomplete_answer` |
| `case_0027_saas_agreement_qa_answer` | qa_answer | 0.963 | `chat:false_negative`, `chat:intent_mismatch` |
| `case_0028_saas_agreement_compound_1` | compound_orchestration | 0.667 | `chat:timeout` |

## DeepEval

Status: `completed`
Source: `agent_trace`

- Skipped agent-trace samples: 25

### saas_agreement
- answer_relevancy: 0.692
- contextual_precision: 0.538
- contextual_recall: 0.750
- contextual_relevancy: 0.388
- faithfulness: 0.986
- aggregate: 0.671

## Notes

- UI, HTML chart rendering, SVG rendering, and browser visual checks are intentionally excluded.
- `reports/evaluation/evaluation_results_full.json` contains complete traces and previews.
- `reports/evaluation/evaluation_failures.json` contains the failure-focused diagnostic view.
