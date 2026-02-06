#include "NVM_Transaction_Flash_IFP.h"
#include "../nvm_chip/NVM_Types.h"

namespace SSD_Components
{
	NVM_Transaction_Flash_IFP::NVM_Transaction_Flash_IFP(Transaction_Source_Type source, stream_id_type stream_id,
		unsigned int data_size_in_byte, LPA_type lpa, PPA_type ppa,
		SSD_Components::User_Request* related_user_IO_request, NVM::memory_content_type content,
		page_status_type read_sectors_bitmap, data_timestamp_type data_timestamp) :
		NVM_Transaction_Flash(source, Transaction_Type::IFP_GEMV, stream_id, data_size_in_byte, lpa, ppa, related_user_IO_request, IO_Flow_Priority_Class::UNDEFINED),
		Content(content), read_sectors_bitmap(read_sectors_bitmap), DataTimeStamp(data_timestamp),
		Partial_dot_product_result(0.0), ECC_retry_needed(false), ECC_retry_count(0), Aggregation_complete(false)
	{
	}

	NVM_Transaction_Flash_IFP::NVM_Transaction_Flash_IFP(Transaction_Source_Type source, stream_id_type stream_id,
		unsigned int data_size_in_byte, LPA_type lpa, PPA_type ppa, const NVM::FlashMemory::Physical_Page_Address& address,
		SSD_Components::User_Request* related_user_IO_request, NVM::memory_content_type content,
		page_status_type read_sectors_bitmap, data_timestamp_type data_timestamp) :
		NVM_Transaction_Flash(source, Transaction_Type::IFP_GEMV, stream_id, data_size_in_byte, lpa, ppa, address, related_user_IO_request, IO_Flow_Priority_Class::UNDEFINED),
		Content(content), read_sectors_bitmap(read_sectors_bitmap), DataTimeStamp(data_timestamp),
		Partial_dot_product_result(0.0), ECC_retry_needed(false), ECC_retry_count(0), Aggregation_complete(false)
	{
	}

	NVM_Transaction_Flash_IFP::NVM_Transaction_Flash_IFP(Transaction_Source_Type source, stream_id_type stream_id,
		unsigned int data_size_in_byte, LPA_type lpa, PPA_type ppa,
		SSD_Components::User_Request* related_user_IO_request, IO_Flow_Priority_Class::Priority priority_class,
		NVM::memory_content_type content,
		page_status_type read_sectors_bitmap, data_timestamp_type data_timestamp) :
		NVM_Transaction_Flash(source, Transaction_Type::IFP_GEMV, stream_id, data_size_in_byte, lpa, ppa, related_user_IO_request, priority_class),
		Content(content), read_sectors_bitmap(read_sectors_bitmap), DataTimeStamp(data_timestamp),
		Partial_dot_product_result(0.0), ECC_retry_needed(false), ECC_retry_count(0), Aggregation_complete(false)
	{
	}
}
