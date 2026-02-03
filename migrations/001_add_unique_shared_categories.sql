ALTER TABLE shared_categories
ADD CONSTRAINT uix_shared_category_user UNIQUE (category_id, user_id);
