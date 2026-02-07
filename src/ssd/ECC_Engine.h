#ifndef ECC_ENGINE_H
#define ECC_ENGINE_H

#include "../sim/Sim_Defs.h"

namespace SSD_Components
{
	class ECC_Engine
	{
	public:
		// Power-law RBER model constructor
		// RBER = epsilon + alpha*(cycles^k) + beta*(cycles^m)*(time^n) + gamma*(cycles^p)*(reads^q)
		ECC_Engine(double epsilon, double alpha, double k,
			double beta, double m, double n,
			double gamma, double p, double q,
			unsigned int page_size_in_bits, unsigned int correction_capability,
			sim_time_type decode_latency, unsigned int max_retries);

		// Returns the number of retries needed (0 = first pass success).
		// Returns -1 if uncorrectable after all retries.
		// pe_cycles: Program/Erase cycle count for the block
		// retention_time_hours: Time since first write to block (in hours)
		// avg_reads_per_page: Average read count per page (block_reads / pages_per_block)
		int Attempt_correction(unsigned int pe_cycles, double retention_time_hours, double avg_reads_per_page);

		// Returns total ECC decode latency in nanoseconds based on retry count.
		// retry_count=0 means first-pass decode; each retry adds decode_latency.
		sim_time_type Get_ECC_latency(int retry_count);

	private:
		// Power-law RBER model coefficients
		double epsilon;          // Base RBER (fresh flash)
		double alpha, k;         // Wear-out: alpha * (cycles^k)
		double beta, m, n;       // Retention loss: beta * (cycles^m) * (time^n)
		double gamma, p, q;      // Read disturb: gamma * (cycles^p) * (reads^q)

		unsigned int page_size_in_bits;
		unsigned int correction_capability; // Max correctable bit errors per page
		sim_time_type decode_latency;       // Latency per decode attempt (ns)
		unsigned int max_retries;           // Max soft-decode retries before failure

		double Calculate_RBER(unsigned int pe_cycles, double retention_time_hours, double avg_reads_per_page);
	};
}

#endif // !ECC_ENGINE_H
