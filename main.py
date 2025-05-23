from flask import Flask, request, jsonify, render_template
import traceback
from config import collection, logger, voice_collection, chat_collection
from utils.mongo_ops import get_proposal_stats, get_voice_data_from_db, get_chat_data_from_db
from datetime import datetime, timedelta, timezone
from flask import Flask
from flask_cors import CORS
from bson.objectid import ObjectId

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",  # Allow all origins
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True  # Enable credentials support
    }
})


@app.route('/test', methods=['GET'])
def index():
    # logger.info("Server is running")
    return {
        "status": True,
        "message": "Sunny Admin Portal is running",    
    }

@app.route('/v1_admin_portal', methods=['GET'])
def admin_portal():
    try:
        days = request.args.get('days', '1')
        page = request.args.get('page', '1')
        per_page = request.args.get('per_page', '50')
        
        # Create a test request context to call proposals_stats internally
        with app.test_request_context(f'/proposals_stats?days={days}&page={page}&per_page={per_page}'):
            response, status_code = proposals_stats()
            
            if status_code != 200:
                raise Exception(f"Failed to fetch proposal stats: {response}")
            
            stats_data = response.get_json()
            
            # Format the stats for the template
            template_stats = {
                'total_proposals': stats_data['data']['Total_Count'],
                'successful_proposals': stats_data['data']['Successful_Count'],
                'unsuccessful_proposals': stats_data['data']['Unsuccessful_Count'],
                'avg_processing_time': round(stats_data['data'].get('Average_Processing_Time') or 0, 2),
                'p90_processing_time': round(stats_data['data'].get('P90_Processing_Time') or 0, 2),
                'p95_processing_time': round(stats_data['data'].get('P95_Processing_Time') or 0, 2),
                'pass_yield': round((stats_data['data'].get('Pass_Yield') or 0) * 100, 2)
            }

        return render_template('admin_portal.html', stats=template_stats, current_page=int(page), per_page=int(per_page))
    
    except Exception as e:
        error_message = f"Error rendering admin portal: {str(e)} {traceback.format_exc()}"
        logger.error(error_message)
        # send_alert_to_slack(f"{error_message}\n{traceback.format_exc()}", "ERROR","ERROR")
        return jsonify({
            "status": False,
            "message": "Internal server error",
            "error": str(e)
        }), 500

@app.route('/database_view', methods=['GET'])
def database_view():
    try:
        # Get pagination parameters from query string
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        search_type = request.args.get('search_type', '')  # Get search type
        search_value = request.args.get('search', '')  # Get search value
        
        # Calculate skip value for pagination
        skip = (page - 1) * per_page
        
        # Build query based on search type and value
        query = {}
        if search_value:
            if search_type == 'id':
                try:
                    query = {'_id': ObjectId(search_value)}
                except:
                    # If invalid ObjectId, return empty results
                    return jsonify({
                        'users': [],
                        'current_page': page,
                        'total_pages': 0,
                        'per_page': per_page,
                        'total_users': 0
                    }), 200
            elif search_type == 'name':
                query = {
                    '$or': [
                        {'firstName': {'$regex': search_value, '$options': 'i'}},
                        {'lastName': {'$regex': search_value, '$options': 'i'}}
                    ]
                }
            elif search_type == 'email':
                query = {'email': {'$regex': search_value, '$options': 'i'}}
        
        # Get total count of documents
        total_users = collection.count_documents(query)
        
        # Get users with pagination and query
        users = collection.find(query).sort('_id', -1).skip(skip).limit(per_page)
        
        # Process users data
        users_data = []
        for user in users:
            # Safely get nested values with fallbacks
            address_data = user.get('address_data', {})
            if isinstance(address_data, str):
                address_data = {}
                
            user_data = {
                'id': str(user.get('_id', '')),
                'email': user.get('email', 'N/A'),
                'name': f"{user.get('firstName', '')} {user.get('lastName', '')}".strip() or 'N/A',
                'address': address_data.get('place_add', 'N/A'),
                'monthly_bill': user.get('monthly_bill', 'N/A'),
                'created_at': user.get('created_at', 'N/A'),
                'freshsales_contact_id': user.get('freshsales_contact_id', 'N/A'),
                'freshsales_account_id': user.get('freshsales_account_id', 'N/A'),
                'freshsales_deal_id': user.get('freshsales_deal_id', 'N/A'),
                'status': 'Success' if user.get('design_creation_status') == 'success' else 'Failed' if user.get('design_creation_status') == 'failed' else 'Pending'
            }
            users_data.append(user_data)
        
        # Calculate total pages
        total_pages = (total_users + per_page - 1) // per_page
        
        return jsonify({
            'users': users_data,
            'current_page': page,
            'total_pages': total_pages,
            'per_page': per_page,
            'total_users': total_users
        }), 200
        
    except Exception as e:
        error_message = f"Error in database view: {str(e)}"
        logger.error(error_message)
        return jsonify({
            "status": False,
            "message": "Internal server error",
            "error": str(e)
        }), 500

@app.route('/summary', methods=['GET'])
def get_summary():
    try:
        # Get total users count
        total_users = collection.count_documents({})
        
        # Get proposals stats for all time
        successful_proposals = collection.count_documents({
            'design_creation_status': 'success',
            'proposal_delivered_at': {'$exists': True}
        })
        
        total_proposals_requested = collection.count_documents({
            'proposal_requested_at': {'$exists': True},
            'design_creation_status': {'$exists': True} ,
            'proposal_delivered_at': {'$exists': True}
        })
        
        return jsonify({
            'status': True,
            'data': {
                'total_users': total_users,
                'successful_proposals': successful_proposals,
                'total_proposals_requested': total_proposals_requested,
                'success_rate': round((successful_proposals / total_proposals_requested * 100), 2) if total_proposals_requested > 0 else 0
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in summary endpoint: {str(e)}")
        return jsonify({
            'status': False,
            'message': 'Internal server error',
            'error': str(e)
        }), 500

@app.route('/chart_stats', methods=['GET'])
def chart_stats():
    try:
        # Get date range parameters (similar to proposals_stats)
        date_str = request.args.get('date')         
        days = request.args.get('days')
        
        # Calculate date range
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                start_of_day = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
                end_of_day = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Please use YYYY-MM-DD'}), 400
        else:
            no_of_days = int(days) if days else 0
            if no_of_days > 0:
                end_of_day = datetime.now(timezone.utc)
                start_of_day = end_of_day - timedelta(days=no_of_days)
            else:
                target_date = datetime.now(timezone.utc)
                start_of_day = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
                end_of_day = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

        # Base query for date range
        date_query = {
            'proposal_requested_at': {
                '$gte': start_of_day,
                '$lte': end_of_day
            }
        }

        # Calculate proposal statistics
        total_proposals = collection.count_documents(date_query)
        delivered_proposals = collection.count_documents({
            **date_query,
            'proposal_delivered_at': {'$exists': True}
        })
        not_delivered_proposals = total_proposals - delivered_proposals

        # Calculate lead source statistics
        lead_sources = {
            'meta': collection.count_documents({**date_query, 'lead_source': 'meta'}),
            'castways': collection.count_documents({**date_query, 'lead_source': 'castways'}),
            'blank': collection.count_documents({**date_query, 'lead_source': ''})
        }

        return jsonify({
            'status': True,
            'data': {
                'proposal_stats': {
                    'total_proposals': total_proposals,
                    'delivered_proposals': delivered_proposals,
                    'not_delivered_proposals': not_delivered_proposals
                },
                'lead_source_stats': lead_sources
            }
        }), 200

    except Exception as e:
        logger.error(f"Error in chart_stats: {str(e)}")
        return jsonify({
            'status': False,
            'message': 'Internal server error',
            'error': str(e)
        }), 500

@app.route('/dashboard', methods=['GET'])
def get_dashboard():
    try:
        # Get date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Parse dates if provided, otherwise use all-time
        date_filter = {}
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                date_filter = {'proposal_requested_at': {'$gte': start, '$lte': end}}
            except ValueError:
                return jsonify({'error': 'Invalid date format. Please use YYYY-MM-DD'}), 400

        successful_proposals = collection.count_documents({
            **date_filter,
            'design_creation_status': 'success',
            'proposal_delivered_at': {'$exists': True}
        })
        
        # Log the final query and results
        query = {
            **date_filter,
            'design_creation_status': {'$exists': True} ,
            'proposal_delivered_at': {'$exists': True}
        }
        total_proposals_requested = collection.count_documents(query)
        logger.info(f"Total proposals requested: {total_proposals_requested}")

        # Calculate average processing time
        pipeline = [
            {'$match': {
                **date_filter,
                'design_creation_status': 'success',
                'proposal_delivered_at': {'$exists': True}    
            }},
            {'$project': {
                'processing_time': {
                    '$divide': [
                        {'$subtract': ['$proposal_delivered_at', '$proposal_requested_at']},
                        60000  # Convert milliseconds to minutes
                    ]
                }
            }},
            {'$group': {
                '_id': None,
                'avg_time': {'$avg': '$processing_time'}
            }}
        ]
        
        avg_result = list(collection.aggregate(pipeline))
        avg_processing_time = round(avg_result[0]['avg_time'], 2) if avg_result else 0
        
        # Calculate lead source statistics
        lead_source_pipeline = [
            {'$match': {
                **date_filter,
                'ref_url_params.lead_source': {'$exists': True}
            }},
            {'$group': {
                '_id': '$ref_url_params.lead_source',
                'count': {'$sum': 1}
            }}
        ]
        
        lead_source_results = list(collection.aggregate(lead_source_pipeline))
        lead_source_stats = {
            source['_id'] if source['_id'] else 'unknown': source['count']
            for source in lead_source_results
        }
        logger.info(f"lead_source_stats: {lead_source_stats}")
        
        
        return jsonify({
            'status': True,
            'data': {
                'successful_proposals': successful_proposals,
                'total_proposals_requested': total_proposals_requested,
                'success_rate': round((successful_proposals / total_proposals_requested * 100), 2) if total_proposals_requested > 0 else 0,
                'average_processing_time': avg_processing_time,  # in minutes
                'lead_source_stats': lead_source_stats  # New field for lead source statistics
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in dashboard endpoint: {str(e)}")
        return jsonify({
            'status': False,
            'message': 'Internal server error',
            'error': str(e)
        }), 500

@app.route('/voice-record/<user_id>', methods=['GET'])
def voice_record(user_id):
    try:
        # Get voice data from MongoDB
        voice_data = get_voice_data_from_db(voice_collection, user_id)
        
        if not voice_data:
            return jsonify({
                'status': False,
                'message': 'No voice data found for this user',
                'data': None
            }), 200
            
        voice_chat = voice_data.get("voice_chat", [])
        session_id = voice_data.get("session_id")
        
        logger.info(f"Voice data retrieved for user {user_id}")
        logger.info(f"Session ID: {session_id}")
        
        return jsonify({
            'status': True,
            'message': 'Voice data retrieved successfully',
            'data': {
                'voice_chat': voice_chat,
                'session_id': session_id
            }
        }), 200

        
    except Exception as e:
        error_message = f"Error retrieving voice data for user {user_id}: {str(e)}"
        logger.error(error_message)
        return jsonify({
            'status': False,
            'message': 'Internal server error',
            'error': str(e)
        }), 500

@app.route('/chat-record/<user_id>', methods=['GET'])
def chat_record(user_id):
    try:
        # Get chat data from MongoDB
        chat_data = get_chat_data_from_db(chat_collection, user_id)
        
        if not chat_data:
            return jsonify({
                'status': False,
                'message': 'No chat data found for this user',
                'data': None
            }), 200
            
        chat_history = chat_data.get("chat_history", [])
        logger.info(f"Chat history=> {chat_history}")
        logger.info(f"Chat data retrieved for user {user_id}")
        
        return jsonify({
            'status': True,
            'message': 'Chat data retrieved successfully',
            'data': {
                'chat_history': chat_history
            }
        }), 200
        
    except Exception as e:
        error_message = f"Error retrieving chat data for user {user_id}: {str(e)}"
        logger.error(error_message)
        return jsonify({
            'status': False,
            'message': 'Internal server error',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("WebSocket Server is running with Redis")
    Flask.run(app, host='0.0.0.0', port=80, debug=True)
    print("WebSocket Server is running with Redis")
