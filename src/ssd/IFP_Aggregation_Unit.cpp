#include "IFP_Aggregation_Unit.h"

namespace SSD_Components
{
	IFP_Aggregation_Unit::IFP_Aggregation_Unit(IFP_Aggregation_Mode mode, sim_time_type dram_access_latency_per_partial)
		: mode(mode), dram_access_latency_per_partial(dram_access_latency_per_partial)
	{
	}

	bool IFP_Aggregation_Unit::Aggregate_partial_result(NVM_Transaction_Flash_IFP* transaction)
	{
		User_Request* user_req = transaction->UserIORequest;
		if (user_req == NULL) {
			return true;
		}

		auto it = pending_aggregations.find(user_req);
		if (it == pending_aggregations.end()) {
			// First partial result for this request -- initialize state
			AggregationState state;
			state.accumulated_result = transaction->Partial_dot_product_result;
			state.completed_count = 1;
			// Count total IFP transactions in this user request
			state.total_count = 0;
			for (auto& tr : user_req->Transaction_list) {
				if (tr->Type == Transaction_Type::IFP_GEMV) {
					state.total_count++;
				}
			}
			// Add 1 for the current transaction (already removed from list by caller)
			state.total_count += 1;

			if (state.completed_count >= state.total_count) {
				transaction->Aggregation_complete = true;
				return true;
			}
			pending_aggregations[user_req] = state;
			return false;
		}

		// Accumulate partial result
		if (mode == IFP_Aggregation_Mode::CHIP_LEVEL) {
			// Chip-level: scalar partial results summed (negligible transfer)
			it->second.accumulated_result += transaction->Partial_dot_product_result;
		} else {
			// Controller-level: each partial vector transferred to DRAM for accumulation
			it->second.accumulated_result += transaction->Partial_dot_product_result;
		}
		it->second.completed_count++;

		if (it->second.completed_count >= it->second.total_count) {
			transaction->Aggregation_complete = true;
			pending_aggregations.erase(it);
			return true;
		}

		return false;
	}

	sim_time_type IFP_Aggregation_Unit::Get_aggregation_latency(User_Request* request)
	{
		if (mode == IFP_Aggregation_Mode::CHIP_LEVEL) {
			// Chip-level: accumulation done on-chip, negligible extra latency
			return 0;
		}

		// Controller-level: one DRAM access per partial result for accumulation
		// The total count has already been cleaned up, so estimate from request size
		unsigned int transaction_count = 0;
		for (auto& tr : request->Transaction_list) {
			if (tr->Type == Transaction_Type::IFP_GEMV) {
				transaction_count++;
			}
		}
		return dram_access_latency_per_partial * transaction_count;
	}
}
