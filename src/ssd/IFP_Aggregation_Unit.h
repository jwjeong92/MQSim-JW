#ifndef IFP_AGGREGATION_UNIT_H
#define IFP_AGGREGATION_UNIT_H

#include <map>
#include "../sim/Sim_Defs.h"
#include "NVM_Transaction_Flash_IFP.h"
#include "User_Request.h"

namespace SSD_Components
{
	enum class IFP_Aggregation_Mode
	{
		CONTROLLER_LEVEL = 0, // Partial results transferred to controller DRAM and accumulated there
		CHIP_LEVEL = 1        // Partial results accumulated on-chip; only final scalar transferred
	};

	class IFP_Aggregation_Unit
	{
	public:
		IFP_Aggregation_Unit(IFP_Aggregation_Mode mode, sim_time_type dram_access_latency_per_partial);

		// Aggregate a partial result from a completed IFP transaction.
		// Returns true when all IFP transactions for this user request are complete.
		bool Aggregate_partial_result(NVM_Transaction_Flash_IFP* transaction);

		// Get the aggregation latency for the completed user request.
		sim_time_type Get_aggregation_latency(User_Request* request);

		IFP_Aggregation_Mode Get_mode() { return mode; }

	private:
		IFP_Aggregation_Mode mode;
		sim_time_type dram_access_latency_per_partial; // Controller-level: DRAM write per partial result

		struct AggregationState
		{
			double accumulated_result;
			unsigned int completed_count;
			unsigned int total_count;
		};

		std::map<User_Request*, AggregationState> pending_aggregations;
	};
}

#endif // !IFP_AGGREGATION_UNIT_H
