-- Query to find photoIDs of photos that are visible to the user whose username is TestUser
SELECT *
FROM photo AS p1
WHERE photoPoster = "TestUser"
OR ( EXISTS (
                SELECT *
                FROM follow
                WHERE follow.username_followed = p1.photoPoster
                AND follow.username_follower = "TestUser"
                AND followstatus = 1)
    OR EXISTS (
                SELECT *
                FROM follow
                WHERE follow.username_follower = p1.photoPoster
                AND follow.username_followed = "TestUser"
                AND followstatus = 1)
    )