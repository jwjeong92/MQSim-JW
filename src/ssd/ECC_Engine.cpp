#include "ECC_Engine.h"
#include <cmath>

namespace SSD_Components
{
	ECC_Engine::ECC_Engine(double epsilon, double alpha, double k,
		double beta, double m, double n,
		double gamma, double p, double q,
		unsigned int page_size_in_bits, unsigned int correction_capability,
		sim_time_type decode_latency, unsigned int max_retries)
		: epsilon(epsilon), alpha(alpha), k(k),
		beta(beta), m(m), n(n),
		gamma(gamma), p(p), q(q),
		page_size_in_bits(page_size_in_bits), correction_capability(correction_capability),
		decode_latency(decode_latency), max_retries(max_retries)
	{
	}

	double ECC_Engine::Calculate_RBER(unsigned int pe_cycles, double retention_time_hours, double avg_reads_per_page)
	{
		// Power-law RBER model: RBER = epsilon + wear-out + retention loss + read disturb
		// retention_time_hours is already in hours (expected by model)
		// avg_reads_per_page = block_read_count / pages_per_block
		double rber = epsilon
			+ alpha * pow(pe_cycles, k)
			+ beta * pow(pe_cycles, m) * pow(retention_time_hours, n)
			+ gamma * pow(pe_cycles, p) * pow(avg_reads_per_page, q);

		return rber;
	}

	int ECC_Engine::Attempt_correction(unsigned int pe_cycles, double retention_time_hours, double avg_reads_per_page)
	{
		double rber = Calculate_RBER(pe_cycles, retention_time_hours, avg_reads_per_page);
		double expected_errors = rber * page_size_in_bits;

		// First-pass hard decode: can correct up to correction_capability errors
		if (expected_errors <= correction_capability) {
			return 0; // Success on first pass
		}

		// Soft-decode retries: each retry increases effective correction capability
		// by ~50% of the base capability (modeling soft-decision LDPC decoding)
		for (unsigned int retry = 1; retry <= max_retries; retry++) {
			double effective_capability = correction_capability * (1.0 + 0.5 * retry);
			if (expected_errors <= effective_capability) {
				return (int)retry;
			}
		}

		return -1; // Uncorrectable
	}

	sim_time_type ECC_Engine::Get_ECC_latency(int retry_count)
	{
		if (retry_count < 0) {
			// Uncorrectable: still incurred all retry attempts
			return decode_latency * (1 + max_retries);
		}
		// Base decode + additional retries
		return decode_latency * (1 + (unsigned int)retry_count);
	}
}
