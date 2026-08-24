# frozen_string_literal: true

module TinyHouseCpee
  InstanceIdentity = Struct.new(
    :instance_id,
    :instance_url,
    :instance_uuid
  )

  FragmentConfig = Struct.new(
    :fragment_id,
    :cpee_base_url,
    :model_path
  )

  DispatchKey = Struct.new(
    :run_id,
    :fragment_id,
    :attempt
  )

  DispatchRequest = Struct.new(
    :run_id,
    :work_order_id,
    :fragment_id,
    :attempt,
    :input_json,
    :parent_instance_uuid,
    :parent_instance_url,
    :parent_callback_url,
    :parent_callback_id,
    :parent_activity,
    keyword_init: true
  )

  DispatchRecord = Struct.new(
    :key,
    :request,
    :definition_sha256,
    :target_cpee_base,
    :deterministic_info,
    :event_token,
    :phase,
    :child_instance_id,
    :child_instance_url,
    :child_instance_uuid,
    :terminal_state,
    :result_json,
    :last_error,
    :callback_salvage,
    :created_at,
    :updated_at,
    keyword_init: true
  )

  DispatchClaim = Struct.new(
    :record,
    :new_record,
    keyword_init: true
  )

  RunRecord = Struct.new(
    :run_id,
    :work_order_id,
    :model_sha256,
    :phase,
    :instance_id,
    :instance_url,
    :instance_uuid,
    :last_error,
    :created_at,
    :updated_at,
    keyword_init: true
  )

  RunClaim = Struct.new(
    :record,
    :new_record,
    keyword_init: true
  )

  module DispatchPhase
    CLAIMED = 'claimed'
    CREATE_UNKNOWN = 'create_unknown'
    READY = 'ready'
    RUNNING = 'running'
    COMPLETION_PENDING = 'completion_pending'
    COMPLETED = 'completed'
    LOST = 'lost'
  end

  module RunPhase
    CLAIMED = 'claimed'
    CREATE_UNKNOWN = 'create_unknown'
    READY = 'ready'
    RUNNING = 'running'
  end
end
