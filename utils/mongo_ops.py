from datetime import datetime, timedelta, timezone
import time
from bson import ObjectId
from config import logger, collection

def get_proposal_stats(collection, start_date, end_date, is_successful):
    try:
        query = {
            'created_at': {
                '$gte': start_date,
                '$lte': end_date
            },
            'email': {'$exists': True, '$ne': None}
        }
        if is_successful:
            query['aurora_data'] = {'$exists': True}
        else:
            query['aurora_data'] = {'$exists': False}

        count = collection.count_documents(query)
        projection = {'email': 1, '_id': 1, 'proposal_requested_at': 1, 'proposal_delivered_at': 1, 'monthly_bill': 1, 'total_wait_time': 1,'created_at': 1, 'updated_at': 1,'address_data.place_add': 1,}
        proposals = list(collection.find(query, projection))
        
        # Process proposals basic data
        serialized_proposals = []
        for proposal in proposals:
            proposal['_id'] = str(proposal['_id'])
            proposal_data = {
                'email': proposal.get('email', 'N/A'),
                'monthly_bill': proposal.get('monthly_bill', 'N/A'),
                'user_id': proposal.get('_id', 'N/A'),
                'address': proposal.get('address_data', {}).get('place_add', 'N/A'),
            }
            
            if is_successful:
                proposal_data.update({
                    'wait_time': proposal.get('total_wait_time', 'N/A'),
                    'proposal_requested_at': proposal.get('proposal_requested_at', 'N/A'),
                    'proposal_delivered_at': proposal.get('proposal_delivered_at', 'N/A') 
                })
            
            serialized_proposals.append(proposal_data)

        return {
            'count': count,
            'proposals': serialized_proposals,
            'proposals': proposals  # Include raw proposals for processing in main.py
        }

    except Exception as e:
        logger.error(f"Error in get_proposal_stats: {str(e)}")
        raise Exception(f"Failed to process proposals: {str(e)}")
    
def get_voice_data_from_db(voice_collection, user_id):
    try:
        voice_data = voice_collection.find_one({"user_id": user_id})
        return voice_data
    
    except Exception as e:
        print(f"Error fetching voice data: {str(e)}")
        raise    

def get_chat_data_from_db(collection, user_id):
    try:
        # Convert string ID to ObjectId for MongoDB query
        object_id = ObjectId(user_id)
        chat_data = collection.find_one({"_id": object_id})
        return chat_data
    except Exception as e:
        logger.error(f"Error fetching chat data from DB: {str(e)}")
        return None
